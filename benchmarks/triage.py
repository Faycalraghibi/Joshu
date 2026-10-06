"""
Tell why benchmark runs failed, from their saved conversations.

Reads a results file written by run.py (default: the latest) and the
transcripts next to it, and gives each failed run one cause:

    provider error    the endpoint failed; says nothing about the model
    no edits          finished (or was stopped) without changing any file
    out of time       killed at the task's timeout
    out of turns      stopped by max_turns, a loop or repeated denials
    untested          edited the code after its last test run, or never ran tests
    gave up failing   its own last test run failed and it finished anyway
    missed cases      its own tests passed, the hidden checks did not

plus signals that explain more: edits that failed to apply, compaction (lost
context), test runs, turns. Several causes can be true; the first in this
order is reported.

Usage:
    python benchmarks/triage.py                       # latest results
    python benchmarks/triage.py benchmarks/results/20261006-101500-fast.json
    python benchmarks/triage.py --all                 # passed runs too
    python benchmarks/triage.py --json                # machine-readable
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import re
import sys
from collections import Counter
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parent
RESULTS = ROOT / "results"


def _bench():
    """run.py, loaded once (for is_infra_error and Result)."""
    if "bench_run" not in sys.modules:
        spec = importlib.util.spec_from_file_location("bench_run", ROOT / "run.py")
        module = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
        sys.modules["bench_run"] = module  # dataclasses look the module up
        spec.loader.exec_module(module)  # type: ignore[union-attr]
    return sys.modules["bench_run"]


EDIT_TOOLS = {"write_file", "replace", "multi_edit", "notebook_edit"}
SHELL_TOOLS = {"run_shell_command"}
SUMMARY_PREFIX = "[Summary of the earlier conversation]"
# A shell command that runs tests
TEST_COMMAND = re.compile(
    r"\b(pytest|unittest|tox|nox|(npm|yarn|pnpm)( run)? test|go test|cargo test|"
    r"make (test|check)|jest|vitest|mocha|phpunit|rspec)\b"
)
# Lines of a failed check worth showing
FAILURE_LINE = re.compile(r"^(FAILED |FAIL:|ERROR:|E  +\w*Error|\w+Error: )")

CAUSES = [
    "provider error",
    "no edits",
    "out of time",
    "out of turns",
    "untested",
    "gave up failing",
    "missed cases",
]


@dataclass
class Signals:
    """What the run's conversation shows."""

    turns: int = 0
    edits: int = 0
    failed_edits: int = 0
    test_runs: int = 0
    last_test_passed: Optional[bool] = None
    edited_after_last_test: bool = False
    compacted: bool = False


@dataclass
class Triage:
    task: str
    passed: bool
    cause: str
    signals: Optional[Signals]
    failing_checks: List[str] = field(default_factory=list)
    transcript: Optional[str] = None


def _ok(output: str) -> bool:
    """Did a tool call succeed (by its JSON result, or its text)?"""
    try:
        data = json.loads(output)
    except ValueError:
        return not output.startswith("Error")
    if isinstance(data, dict):
        if data.get("success") is False or data.get("error"):
            return False
        if "exit_code" in data:
            return data["exit_code"] == 0
    return True


def read_signals(messages: List[Dict[str, Any]]) -> Signals:
    signals = Signals()
    outputs = {
        m.get("tool_call_id"): str(m.get("content") or "")
        for m in messages
        if m.get("role") == "tool"
    }
    for message in messages:
        content = message.get("content")
        if message.get("role") == "user" and str(content or "").startswith(SUMMARY_PREFIX):
            signals.compacted = True
        if message.get("role") != "assistant":
            continue
        signals.turns += 1
        for call in message.get("tool_calls") or []:
            function = call.get("function") or {}
            name = str(function.get("name") or "")
            output = outputs.get(call.get("id"), "")
            if name in EDIT_TOOLS:
                if _ok(output):
                    signals.edits += 1
                    if signals.test_runs:
                        signals.edited_after_last_test = True
                else:
                    signals.failed_edits += 1
            elif name in SHELL_TOOLS:
                try:
                    command = str(json.loads(function.get("arguments") or "{}").get("command", ""))
                except (ValueError, AttributeError):
                    command = ""
                if TEST_COMMAND.search(command):
                    signals.test_runs += 1
                    signals.last_test_passed = _ok(output)
                    signals.edited_after_last_test = False
    return signals


def failing_checks(check_output: str, limit: int = 3) -> List[str]:
    lines = [line.strip() for line in check_output.splitlines() if FAILURE_LINE.match(line.strip())]
    return [line[:120] for line in lines[:limit]]


def cause_of(result: Dict[str, Any], signals: Optional[Signals]) -> str:
    bench = _bench()
    known = {k: v for k, v in result.items() if k in bench.Result.__dataclass_fields__}
    if bench.is_infra_error(bench.Result(**known)):
        return "provider error"
    if result.get("passed"):
        return "passed"
    if signals is not None and signals.edits == 0:
        return "no edits"
    if result.get("error") == "timeout":
        return "out of time"
    if result.get("stopped"):
        return "out of turns"
    if signals is None:
        return "no transcript"
    if signals.test_runs == 0 or signals.edited_after_last_test:
        return "untested"
    if signals.last_test_passed is False:
        return "gave up failing"
    return "missed cases"


def triage_file(path: Path) -> List[Triage]:
    data = json.loads(path.read_text(encoding="utf-8"))
    triaged = []
    for result in data.get("results") or []:
        signals = None
        transcript = result.get("transcript")
        if transcript and (path.parent / transcript).is_file():
            session = json.loads((path.parent / transcript).read_text(encoding="utf-8"))
            signals = read_signals(session.get("messages") or [])
        triaged.append(
            Triage(
                task=result["task"],
                passed=bool(result.get("passed")),
                cause=cause_of(result, signals),
                signals=signals,
                failing_checks=[]
                if result.get("passed")
                else failing_checks(result.get("check_output") or ""),
                transcript=transcript,
            )
        )
    return triaged


def latest_results() -> Optional[Path]:
    files = sorted(RESULTS.glob("*.json"), key=lambda p: p.stat().st_mtime)
    return files[-1] if files else None


def print_report(triaged: List[Triage], show_all: bool = False) -> None:
    rows = [t for t in triaged if show_all or not t.passed]
    header = f"{'task':24} {'cause':18} {'turns':>5} {'edits':>5} {'bad':>4} {'tests':>5} {'last':>5}  notes"
    print(header)
    print("-" * len(header))
    for t in rows:
        s = t.signals
        last = (
            "-"
            if s is None or s.last_test_passed is None
            else ("pass" if s.last_test_passed else "fail")
        )
        notes = []
        if s is not None and s.compacted:
            notes.append("compacted")
        if t.failing_checks:
            notes.append(t.failing_checks[0])
        print(
            f"{t.task:24} {t.cause:18} "
            f"{s.turns if s else '-':>5} {s.edits if s else '-':>5} "
            f"{s.failed_edits if s else '-':>4} {s.test_runs if s else '-':>5} {last:>5}  "
            + "; ".join(notes)[:70]
        )
    counts = Counter(t.cause for t in triaged if not t.passed)
    print("-" * len(header))
    passed = sum(t.passed for t in triaged)
    print(f"{passed}/{len(triaged)} passed. Failures by cause:")
    for cause in CAUSES + sorted(set(counts) - set(CAUSES)):
        if counts.get(cause):
            print(f"  {cause:18} {counts[cause]}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("results", nargs="*", type=Path, help="Results files (default: latest)")
    parser.add_argument("--all", action="store_true", help="Show passed runs too")
    parser.add_argument("--json", action="store_true", help="Print JSON instead of a table")
    args = parser.parse_args()

    files = args.results or [p for p in [latest_results()] if p]
    if not files:
        print("No results yet: run benchmarks/run.py first.", file=sys.stderr)
        return 1
    triaged = [t for path in files for t in triage_file(path)]
    if args.json:
        print(json.dumps([asdict(t) for t in triaged], indent=2))
    else:
        for path in files:
            print(f"# {path.name}")
        print_report(triaged, args.all)
    return 0


if __name__ == "__main__":
    sys.exit(main())
