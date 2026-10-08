"""
Background jobs: a request that runs on its own, after the terminal closes.

`joshu run --background "<prompt>"` (or /background in a session) makes a
worktree of the project (HEAD plus uncommitted changes, see
joshu.core.worktrees), starts a detached Joshu process there and returns at
once. The job works without anyone to approve, so it runs in accept_edits
mode by default: edits run, shell commands are refused unless allowed by
your permission rules (choose bypass for more). When it finishes, its work is
committed on a branch `joshu/job-<id>`, the worktree is removed, and the
result is recorded. `joshu jobs` lists them; `show` gives a job's answer, its
log and changed files; `apply` puts its work into the working tree;
`stop` ends a running one.

Job records live in ~/.joshu/jobs/<id>/ (job.json, output.log).
"""

from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

RUNNING, DONE, FAILED, STOPPED, LOST = "running", "done", "failed", "stopped", "lost"


class JobError(Exception):
    """A job can't be started, found or applied."""


@dataclass
class Job:
    id: str
    prompt: str
    cwd: str  # the project the job was started from
    status: str = RUNNING
    permission_mode: str = "accept_edits"
    model: Optional[str] = None
    provider: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))
    finished_at: Optional[str] = None
    pid: Optional[int] = None
    repo: str = ""
    worktree: str = ""
    branch: str = ""
    base: str = ""
    seeded: bool = False
    session_id: Optional[str] = None
    result: str = ""
    error: str = ""
    files: List[str] = field(default_factory=list)
    stat: str = ""
    applied: bool = False

    @property
    def directory(self) -> Path:
        return jobs_dir() / self.id

    @property
    def log_path(self) -> Path:
        return self.directory / "output.log"

    def save(self) -> None:
        self.directory.mkdir(parents=True, exist_ok=True)
        tmp = self.directory / "job.json.tmp"
        tmp.write_text(json.dumps(asdict(self), indent=1), encoding="utf-8")
        tmp.replace(self.directory / "job.json")


def jobs_dir() -> Path:
    from joshu.core.paths import joshu_home

    return joshu_home() / "jobs"


def load(job_id: str) -> Job:
    """A job by id (or a unique prefix)."""
    root = jobs_dir()
    matches = (
        sorted(p for p in root.glob(f"{job_id}*") if (p / "job.json").is_file())
        if root.is_dir()
        else []
    )
    if not matches:
        raise JobError(f"No job '{job_id}' (see `joshu jobs`)")
    if len(matches) > 1:
        raise JobError(f"'{job_id}' matches several jobs: {', '.join(p.name for p in matches)}")
    data = json.loads((matches[0] / "job.json").read_text(encoding="utf-8"))
    job = Job(**{k: v for k, v in data.items() if k in Job.__dataclass_fields__})
    if job.status == RUNNING and job.pid and not _alive(job.pid):
        job.status, job.error = LOST, "the job's process ended without recording a result"
        job.save()
    return job


def list_jobs() -> List[Job]:
    """All jobs, newest first."""
    root = jobs_dir()
    if not root.is_dir():
        return []
    jobs = []
    for directory in root.iterdir():
        if (directory / "job.json").is_file():
            try:
                jobs.append(load(directory.name))
            except (JobError, ValueError, TypeError):
                continue
    return sorted(jobs, key=lambda j: j.created_at, reverse=True)


def start(
    prompt: str,
    cwd: Path,
    permission_mode: str = "accept_edits",
    model: Optional[str] = None,
    provider: Optional[str] = None,
    spawn: bool = True,
) -> Job:
    """Make the job's worktree and start it detached (`spawn=False`: only prepare it)."""
    from joshu.core.worktrees import WorktreeError, create

    job = Job(
        id=uuid.uuid4().hex[:8],
        prompt=prompt,
        cwd=str(Path(cwd).resolve()),
        permission_mode=permission_mode,
        model=model,
        provider=provider,
    )
    try:
        worktree = create(Path(cwd), f"job-{job.id}")
    except WorktreeError as e:
        raise JobError(f"background jobs need a git repository: {e}") from e
    job.repo, job.worktree, job.branch = str(worktree.repo), str(worktree.path), worktree.branch
    job.base, job.seeded = worktree.base, worktree.seeded
    job.save()
    if spawn:
        job.pid = _spawn(job)
        job.save()
    return job


def _spawn(job: Job) -> int:
    """Start `python -m joshu.core.jobs <id>` detached from this terminal."""
    log = open(job.log_path, "ab")
    kwargs: Dict[str, Any] = {
        "stdout": log,
        "stderr": subprocess.STDOUT,
        "stdin": subprocess.DEVNULL,
    }
    if os.name == "nt":
        flags = subprocess.CREATE_NEW_PROCESS_GROUP | getattr(subprocess, "DETACHED_PROCESS", 0x8)
        kwargs["creationflags"] = flags | getattr(subprocess, "CREATE_NO_WINDOW", 0)
    else:
        kwargs["start_new_session"] = True
    import joshu

    # The child imports the same Joshu, wherever it was loaded from (a relative
    # PYTHONPATH wouldn't hold from the worktree)
    package_root = str(Path(joshu.__file__).resolve().parents[1])
    paths = [package_root, *filter(None, os.environ.get("PYTHONPATH", "").split(os.pathsep))]
    env = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONPATH": os.pathsep.join(paths)}
    process = subprocess.Popen(
        [sys.executable, "-m", "joshu.core.jobs", job.id], cwd=job.worktree, env=env, **kwargs
    )
    log.close()
    return process.pid


def run(job_id: str, client: Any = None) -> Job:
    """The job's own process: do the request in the worktree, then record the outcome."""
    from joshu.core.worktrees import Worktree, commit, remove
    from joshu.sdk import Session

    job = load(job_id)
    job.pid = os.getpid()
    job.save()
    worktree = Worktree(
        repo=Path(job.repo),
        path=Path(job.worktree),
        branch=job.branch,
        base=job.base,
        seeded=job.seeded,
    )
    try:
        os.chdir(job.worktree)
        with Session(
            cwd=job.worktree,
            permission_mode=job.permission_mode,
            model=job.model,
            provider=job.provider,
            persist=True,
            client=client,
        ) as session:
            result = session.send(job.prompt)
        job.session_id, job.result = result.session_id, result.text
        job.files = commit(worktree, f"Joshu job {job.id}: {' '.join(job.prompt.split())[:60]}")
        if job.files:
            from joshu.core.worktrees import _git

            job.stat = _git(worktree.repo, "diff", "--stat", worktree.base, worktree.branch).strip()
        job.status = DONE
    except BaseException as e:  # record why, even for Ctrl+C or a kill
        job.status, job.error = FAILED, f"{type(e).__name__}: {e}"
        if not isinstance(e, Exception):
            raise
    finally:
        job.finished_at = datetime.now().isoformat(timespec="seconds")
        os.chdir(job.repo)
        # Keep the branch when there is work on it; the worktree directory goes
        remove(worktree, delete_branch=not job.files)
        job.save()
    return job


def apply(job_id: str, before_apply: Optional[Callable[[List[Path]], None]] = None) -> Job:
    """Put a finished job's work into the working tree (or say why it stays on its branch)."""
    from joshu.core.worktrees import Outcome, Worktree, apply_work

    job = load(job_id)
    if job.status != DONE:
        raise JobError(f"Job {job.id} is {job.status}; only finished jobs can be applied")
    if job.applied:
        raise JobError(f"Job {job.id} was already applied")
    if not job.files:
        raise JobError(f"Job {job.id} changed no files")
    worktree = Worktree(
        repo=Path(job.repo),
        path=Path(job.worktree),
        branch=job.branch,
        base=job.base,
        seeded=job.seeded,
    )
    outcome = apply_work(worktree, Outcome(files=list(job.files), stat=job.stat), before_apply)
    if not outcome.applied:
        raise JobError(outcome.message)
    from joshu.core.worktrees import _git

    _git(worktree.repo, "branch", "-q", "-D", job.branch, check=False)
    job.applied = True
    job.save()
    return job


def stop(job_id: str) -> Job:
    """End a running job and drop its worktree and branch."""
    from joshu.core.worktrees import Worktree, remove

    job = load(job_id)
    if job.status != RUNNING:
        raise JobError(f"Job {job.id} isn't running ({job.status})")
    if job.pid:
        _kill(job.pid)
    remove(
        Worktree(repo=Path(job.repo), path=Path(job.worktree), branch=job.branch, base=job.base),
        delete_branch=True,
    )
    job.status, job.finished_at = STOPPED, datetime.now().isoformat(timespec="seconds")
    job.save()
    return job


def log_tail(job: Job, lines: int = 40) -> str:
    try:
        text = job.log_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""
    return "\n".join(text.splitlines()[-lines:])


def _alive(pid: int) -> bool:
    if os.name == "nt":
        import ctypes

        handle = ctypes.windll.kernel32.OpenProcess(0x1000, False, pid)  # QUERY_LIMITED_INFORMATION
        if not handle:
            return False
        code = ctypes.c_ulong()
        ctypes.windll.kernel32.GetExitCodeProcess(handle, ctypes.byref(code))
        ctypes.windll.kernel32.CloseHandle(handle)
        return code.value == 259  # STILL_ACTIVE
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _kill(pid: int) -> None:
    if os.name == "nt":
        subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True)
        return
    try:
        os.killpg(pid, signal.SIGTERM)
    except (ProcessLookupError, PermissionError):
        pass


if __name__ == "__main__":
    run(sys.argv[1])
