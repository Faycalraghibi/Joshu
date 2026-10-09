"""
Run Joshu on the benchmark tasks and report how many it solves.

Each task in benchmarks/tasks/<name>/ has:
    task.yaml   prompt (sent to the agent), check (command run afterwards),
                optional timeout (seconds, default 600) and tier (easy or hard)
    files/      the project the agent works on
    check/      hidden test files, copied in only after the agent finishes

benchmarks/solutions/<name>/ holds a reference solution (files laid over
files/, plus a .deleted list). The agent never sees it; --verify uses it to
check that every task fails as given and passes when solved.

Usage:
    python benchmarks/run.py --provider nvidia --model nvidia/nemotron-3.5-lightning-30b-a3b
    python benchmarks/run.py --model fast --tasks fix-bug,off-by-one --repeat 3
    python benchmarks/run.py --permission-mode bypass   # let the agent run tests itself
    python benchmarks/run.py --tier hard                # only the hard tasks
    python benchmarks/run.py --verify                   # check the tasks themselves

Each run gets a fresh copy of the task in a temporary directory and a
temporary JOSHU_HOME holding a copy of your user config (MCP off unless --mcp),
so your sessions and settings are untouched. Results are printed as a table and
saved as JSON under benchmarks/results/, with each run's conversation (also of
runs that timed out) in a folder of the same name; `benchmarks/triage.py`
reads them to tell why runs failed.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional

import yaml

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent
TASKS = ROOT / "tasks"
SOLUTIONS = ROOT / "solutions"
TIERS = ("easy", "hard")


@dataclass
class Result:
    task: str
    passed: bool
    seconds: float
    turns: Optional[int] = None
    tool_calls: Optional[int] = None
    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None
    cost_usd: Optional[float] = None
    stopped: Optional[str] = None
    error: str = ""
    answer: str = field(default="", repr=False)
    check_output: str = field(default="", repr=False)
    transcript: Optional[str] = None  # the run's saved conversation, relative to results/


def task_spec(task: Path) -> Dict[str, Any]:
    spec = yaml.safe_load((task / "task.yaml").read_text(encoding="utf-8"))
    spec.setdefault("tier", "easy")
    return spec


def load_tasks(names: Optional[List[str]], tier: Optional[str] = None) -> List[Path]:
    tasks = sorted(p for p in TASKS.iterdir() if (p / "task.yaml").is_file())
    if tier:
        tasks = [t for t in tasks if task_spec(t)["tier"] == tier]
    if names:
        wanted = set(names)
        unknown = wanted - {t.name for t in tasks}
        if unknown:
            sys.exit(f"Unknown task(s): {', '.join(sorted(unknown))}")
        tasks = [t for t in tasks if t.name in wanted]
    return tasks


def make_home(
    base: Path, mcp: bool, overrides: Optional[Dict[str, Any]] = None, sessions: bool = False
) -> Path:
    """
    A JOSHU_HOME with a copy of the user config (providers, named models).
    `sessions`: save the conversation in it (it is saved after every tool round).
    """
    from joshu.core.paths import joshu_home

    home = base / "home"
    home.mkdir()
    config: Dict[str, Any] = {}
    user_config = joshu_home() / "config.yaml"
    if user_config.is_file():
        config = yaml.safe_load(user_config.read_text(encoding="utf-8")) or {}
    if not mcp:
        config["mcp_enabled"] = False
    config["save_sessions"] = sessions
    config.update(overrides or {})
    (home / "config.yaml").write_text(yaml.safe_dump(config), encoding="utf-8")
    return home


def parse_overrides(items: Optional[List[str]]) -> Dict[str, Any]:
    """`--set self_review=false` -> {"self_review": False} (values parsed as YAML)."""
    overrides: Dict[str, Any] = {}
    for item in items or []:
        key, sep, value = item.partition("=")
        if not sep or not key.strip():
            sys.exit(f"--set expects key=value, got {item!r}")
        overrides[key.strip()] = yaml.safe_load(value)
    return overrides


def keep_transcript(home: Path, dest: Optional[Path]) -> Optional[Path]:
    """Copy the run's saved conversation out of its temporary JOSHU_HOME."""
    if dest is None:
        return None
    saved = sorted((home / "sessions").glob("*.json"), key=lambda p: p.stat().st_mtime)
    if not saved:
        return None
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(saved[-1], dest)
    return dest


def run_task(
    task: Path,
    args: argparse.Namespace,
    env: Dict[str, str],
    transcript: Optional[Path] = None,
) -> Result:
    """One run; `transcript`: where to keep its conversation."""
    spec = yaml.safe_load((task / "task.yaml").read_text(encoding="utf-8"))
    timeout = int(spec.get("timeout", args.timeout))

    with tempfile.TemporaryDirectory(prefix=f"joshu-bench-{task.name}-") as tmp:
        base = Path(tmp)
        work = base / "work"
        shutil.copytree(task / "files", work)
        home = make_home(base, args.mcp, parse_overrides(args.set), sessions=transcript is not None)
        run_env = {**env, "JOSHU_HOME": str(home)}

        def kept() -> Optional[str]:
            path = keep_transcript(home, transcript)
            return str(path.relative_to(ROOT / "results")) if path else None

        command = [sys.executable, "-m", "joshu", "run", spec["prompt"]]
        command += ["--output-format", "json", "--permission-mode", args.permission_mode]
        if args.provider:
            command += ["--provider", args.provider]
        if args.model:
            command += ["--model", args.model]

        start = time.monotonic()
        try:
            agent = run_with_timeout(command, work, run_env, timeout)
        except subprocess.TimeoutExpired:
            result = Result(task.name, False, time.monotonic() - start, error="timeout")
            result.transcript = kept()
            return result
        seconds = time.monotonic() - start

        result = Result(task.name, False, seconds)
        payload = _last_json(agent.stdout)
        if payload is None:
            result.error = (agent.stderr or agent.stdout).strip()[-500:] or "no output"
        else:
            usage = payload.get("usage") or {}
            result.turns = payload.get("turns")
            result.tool_calls = payload.get("tool_calls")
            result.prompt_tokens = usage.get("prompt_tokens")
            result.completion_tokens = usage.get("completion_tokens")
            result.cost_usd = payload.get("cost_usd")
            result.stopped = payload.get("stopped")
            result.answer = str(payload.get("result") or "")[-2000:]

        # Hidden checks go in only now, so the agent can't edit them
        result.passed, result.check_output = run_check(task, spec, work, run_env)
        result.transcript = kept()
        return result


@contextlib.contextmanager
def keep_awake() -> Iterator[None]:
    """Keep the computer from sleeping while the benchmark runs."""
    if os.name == "nt":
        import ctypes

        es_continuous, es_system_required = 0x80000000, 0x00000001
        kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
        kernel32.SetThreadExecutionState(es_continuous | es_system_required)
        try:
            yield
        finally:
            kernel32.SetThreadExecutionState(es_continuous)
        return
    caffeinate = shutil.which("caffeinate")  # macOS
    process = subprocess.Popen([caffeinate, "-i"]) if caffeinate else None
    try:
        yield
    finally:
        if process is not None:
            process.terminate()


def run_with_timeout(
    command: List[str], cwd: Path, env: Dict[str, str], timeout: float
) -> "subprocess.CompletedProcess[str]":
    """
    Run the agent; on timeout kill it *and everything it started*.

    subprocess.run(timeout=...) kills only the direct child and then waits for
    the output pipes to close, which never happens while a grandchild (a test
    run or server the agent started) still holds them: runs went on for
    hours past their limit.
    """
    flags = subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0
    process = subprocess.Popen(
        command,
        cwd=cwd,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        creationflags=flags,
        start_new_session=os.name != "nt",
    )
    try:
        stdout, stderr = process.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        kill_tree(process)
        try:
            process.communicate(timeout=10)
        except subprocess.TimeoutExpired:
            pass
        raise
    return subprocess.CompletedProcess(command, process.returncode, stdout, stderr)


def kill_tree(process: "subprocess.Popen[str]") -> None:
    """Kill a process and all its descendants."""
    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/F", "/T", "/PID", str(process.pid)],
            capture_output=True,
        )
    else:
        import signal

        try:
            os.killpg(process.pid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            pass
    process.kill()


def run_check(task: Path, spec: Dict[str, Any], work: Path, env: Dict[str, str]) -> tuple:
    """Copy in the hidden checks and run them: (passed, output)."""
    if (task / "check").is_dir():
        shutil.copytree(task / "check", work, dirs_exist_ok=True)
    check = subprocess.run(
        [sys.executable if part == "python" else part for part in shlex.split(spec["check"])],
        cwd=work,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=300,
    )
    return check.returncode == 0, (check.stdout + check.stderr).strip()[-2000:]


def apply_solution(task: Path, work: Path) -> None:
    """Lay the reference solution over a copy of the task's files."""
    solution = SOLUTIONS / task.name
    deleted = solution / ".deleted"
    if deleted.is_file():
        for name in deleted.read_text(encoding="utf-8").split():
            (work / name).unlink(missing_ok=True)
    for path in solution.rglob("*"):
        if path.is_file() and path.name != ".deleted":
            target = work / path.relative_to(solution)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, target)


def verify_task(task: Path, env: Dict[str, str]) -> List[str]:
    """Problems with a task: its checks must fail as given and pass when solved."""
    spec = task_spec(task)
    problems = []
    if spec["tier"] not in TIERS:
        problems.append(f"unknown tier {spec['tier']!r}")
    if not (task / "check").is_dir():
        problems.append("no check/ directory")
    with tempfile.TemporaryDirectory(prefix=f"joshu-verify-{task.name}-") as tmp:
        work = Path(tmp) / "work"
        shutil.copytree(task / "files", work)
        passed, _ = run_check(task, spec, work, env)
        if passed:
            problems.append("the checks pass before any change (the task tests nothing)")
    if not (SOLUTIONS / task.name).is_dir():
        if spec["tier"] == "hard":
            problems.append("no reference solution")
        return problems
    with tempfile.TemporaryDirectory(prefix=f"joshu-verify-{task.name}-") as tmp:
        work = Path(tmp) / "work"
        shutil.copytree(task / "files", work)
        apply_solution(task, work)
        passed, output = run_check(task, spec, work, env)
        if not passed:
            problems.append("the reference solution fails the checks:\n" + output[-800:])
    return problems


def _last_json(stdout: str) -> Optional[Dict[str, Any]]:
    for line in reversed(stdout.strip().splitlines()):
        line = line.strip()
        if line.startswith("{"):
            try:
                return json.loads(line)
            except ValueError:
                continue
    return None


# Failures that say nothing about the model: the endpoint couldn't be reached
INFRA_ERRORS = (
    "Connection error",
    "request failed: Connection",
    "timed out",
    "Read timeout",
    # The provider answered with a server error or a rate limit (after retries)
    "request failed: HTTP 5",
    "request failed: HTTP 429",
)


def is_infra_error(result: Result) -> bool:
    # The error comes from the terminal output, wrapped at its width
    error = " ".join(result.error.split())
    return (
        not result.passed
        and result.turns is None
        and any(marker in error for marker in INFRA_ERRORS)
    )


def print_table(results: List[Result]) -> None:
    header = f"{'task':24} {'result':6} {'time':>7} {'turns':>5} {'tools':>5} {'tokens':>8}  note"
    print(header)
    print("-" * len(header))
    for r in results:
        tokens = (r.prompt_tokens or 0) + (r.completion_tokens or 0)
        note = r.error.splitlines()[-1][:60] if r.error else (r.stopped or "")
        outcome = "PASS" if r.passed else ("error" if is_infra_error(r) else "fail")
        print(
            f"{r.task:24} {outcome:6} {r.seconds:6.0f}s "
            f"{r.turns if r.turns is not None else '-':>5} "
            f"{r.tool_calls if r.tool_calls is not None else '-':>5} "
            f"{tokens or '-':>8}  {note}"
        )
    passed = sum(r.passed for r in results)
    errors = sum(is_infra_error(r) for r in results)
    counted = len(results) - errors
    total_tokens = sum((r.prompt_tokens or 0) + (r.completion_tokens or 0) for r in results)
    print("-" * len(header))
    print(
        f"{passed}/{counted} passed ({passed / max(1, counted):.0%}), "
        f"{total_tokens:,} tokens, {sum(r.seconds for r in results):.0f}s"
        + (f"; {errors} not counted (endpoint unreachable)" if errors else "")
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--provider", help="Provider (default: your configured one)")
    parser.add_argument("--model", help="Model id or named model (default: configured)")
    parser.add_argument("--tasks", help="Comma-separated task names (default: all)")
    parser.add_argument("--repeat", type=int, default=1, help="Runs per task")
    parser.add_argument(
        "--permission-mode",
        default="accept_edits",
        choices=["accept_edits", "bypass"],
        help="accept_edits (default): edits run, shell commands are refused; "
        "bypass: the agent may also run commands (it runs unattended in a temp dir)",
    )
    parser.add_argument("--timeout", type=int, default=600, help="Seconds per task")
    parser.add_argument("--mcp", action="store_true", help="Load MCP servers (off by default)")
    parser.add_argument("--list", action="store_true", help="List tasks and exit")
    parser.add_argument("--tier", choices=TIERS, help="Only tasks of this tier")
    parser.add_argument(
        "--set",
        action="append",
        metavar="KEY=VALUE",
        help="Override a Joshu setting for the runs (repeatable), e.g. --set self_review=false",
    )
    parser.add_argument(
        "--no-transcripts",
        action="store_true",
        help="Don't keep each run's conversation next to the results",
    )
    parser.add_argument(
        "--max-errors",
        type=int,
        default=3,
        help="Stop after this many runs in a row that couldn't reach the endpoint",
    )
    parser.add_argument(
        "--verify",
        action="store_true",
        help="Check the tasks themselves (fail as given, pass when solved); runs no model",
    )
    args = parser.parse_args()

    tasks = load_tasks(args.tasks.split(",") if args.tasks else None, args.tier)
    if args.list:
        for task in tasks:
            spec = task_spec(task)
            print(f"{task.name:24} {spec['tier']:5} {' '.join(spec['prompt'].split())[:62]}")
        return 0
    if args.verify:
        failed = 0
        for task in tasks:
            problems = verify_task(task, {**os.environ, "PYTHONIOENCODING": "utf-8"})
            print(f"{task.name:24} {'ok' if not problems else 'PROBLEM'}")
            for problem in problems:
                print("    " + problem)
            failed += bool(problems)
        return 1 if failed else 0

    sys.path.insert(0, str(REPO / "src"))
    from dotenv import dotenv_values

    env = {**os.environ}
    for key, value in dotenv_values(REPO / ".env").items():
        if value is not None:
            env.setdefault(key, value)
    env["PYTHONPATH"] = os.pathsep.join(filter(None, [str(REPO / "src"), env.get("PYTHONPATH")]))
    env["PYTHONIOENCODING"] = "utf-8"

    out_dir = ROOT / "results"
    out_dir.mkdir(exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    name = (args.model or "default").replace("/", "_").replace(":", "_")
    out = out_dir / f"{stamp}-{name}.json"
    transcripts = None if args.no_transcripts else out.with_suffix("")

    def save() -> None:
        # After every task, so an interrupted run keeps what it measured
        payload = {
            "provider": args.provider,
            "model": args.model,
            "permission_mode": args.permission_mode,
            "settings": parse_overrides(args.set),
            "results": [asdict(r) for r in results],
        }
        out.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    results: List[Result] = []
    errors_in_a_row = 0
    # A machine that sleeps mid-run drops the network and stretches task times
    with keep_awake():
        for task in tasks:
            for attempt in range(args.repeat):
                label = task.name + (f" #{attempt + 1}" if args.repeat > 1 else "")
                print(f"running {label}...", file=sys.stderr, flush=True)
                dest = transcripts / f"{label.replace(' #', '-')}.json" if transcripts else None
                result = run_task(task, args, env, dest)
                results.append(result)
                save()
                outcome = (
                    "PASS" if result.passed else ("error" if is_infra_error(result) else "fail")
                )
                print(f"  {label}: {outcome} ({result.seconds:.0f}s)", file=sys.stderr, flush=True)
                errors_in_a_row = errors_in_a_row + 1 if is_infra_error(result) else 0
                if errors_in_a_row >= args.max_errors:
                    print(
                        f"Stopping: {errors_in_a_row} runs in a row couldn't reach the endpoint.",
                        file=sys.stderr,
                    )
                    break
            if errors_in_a_row >= args.max_errors:
                break

    print_table(results)
    print(f"Saved {out.relative_to(REPO)}")
    return 0 if results and all(r.passed for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
