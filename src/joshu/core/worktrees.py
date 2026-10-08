"""
Git worktrees for sub-agents that edit: each gets its own checkout of HEAD on
a new branch, so several can change code at once without touching each other
or the user's working tree. When one finishes, its work is committed on the
branch and applied to the working tree, unless it touches files with
uncommitted changes there; then it stays on the branch for the user to merge.

Worktrees live under ~/.joshu/worktrees/ (outside the repository).
"""

from __future__ import annotations

import re
import shutil
import subprocess
import threading
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, List, Optional

# Applying to the working tree one at a time (parallel sub-agents)
_apply_lock = threading.Lock()


class WorktreeError(Exception):
    """A worktree couldn't be created or its work applied."""


@dataclass
class Worktree:
    repo: Path  # the repository's top level
    path: Path
    branch: str
    base: str  # the commit the sub-agent's work starts from (after the seed)
    # The working tree's uncommitted changes were copied in (a "seed" commit)
    seeded: bool = False


@dataclass
class Outcome:
    """What became of a sub-agent's work."""

    files: List[str] = field(default_factory=list)  # changed, relative to the repository
    applied: bool = False
    branch: Optional[str] = None  # kept when not applied
    stat: str = ""  # git diff --stat
    message: str = ""


def _git(cwd: Path, *args: str, input: Optional[str] = None, check: bool = True) -> str:
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=cwd,
            input=input,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=120,
        )
    except (OSError, subprocess.SubprocessError) as e:
        raise WorktreeError(f"git {args[0]} failed: {e}") from e
    if check and result.returncode != 0:
        raise WorktreeError(
            f"git {' '.join(args[:2])} failed: {(result.stderr or result.stdout).strip()}"
        )
    return result.stdout


def repo_root(cwd: Path) -> Optional[Path]:
    """The repository's top level, or None outside a git repository with commits."""
    try:
        top = _git(cwd, "rev-parse", "--show-toplevel").strip()
        _git(cwd, "rev-parse", "--verify", "HEAD")
    except WorktreeError:
        return None
    return Path(top).resolve() if top else None


def worktrees_dir() -> Path:
    from joshu.core.paths import joshu_home

    return joshu_home() / "worktrees"


def create(cwd: Path, label: str) -> Worktree:
    """A new worktree of the repository at `cwd`, on a new branch from HEAD."""
    repo = repo_root(cwd)
    if repo is None:
        raise WorktreeError("editing sub-agents need a git repository with at least one commit")
    slug = re.sub(r"[^a-z0-9]+", "-", label.lower()).strip("-")[:30] or "task"
    short = uuid.uuid4().hex[:6]
    branch = f"joshu/{slug}-{short}"
    path = worktrees_dir() / f"{repo.name}-{slug}-{short}"
    path.parent.mkdir(parents=True, exist_ok=True)
    base = _git(repo, "rev-parse", "HEAD").strip()
    _git(repo, "worktree", "add", "-q", "-b", branch, str(path), base)
    worktree = Worktree(repo=repo, path=path.resolve(), branch=branch, base=base)
    try:
        _seed(worktree)
    except (WorktreeError, OSError, subprocess.SubprocessError) as e:
        remove(worktree, delete_branch=True)
        raise WorktreeError(f"couldn't copy the uncommitted changes into the worktree: {e}") from e
    return worktree


MAX_UNTRACKED_BYTES = 5_000_000  # bigger untracked files aren't copied


def _seed(worktree: Worktree) -> None:
    """
    Copy the working tree's uncommitted changes (tracked and untracked, not
    ignored) into the worktree and commit them, so the sub-agent sees the
    project as it is and its own work is the diff from there.
    """
    repo, path = worktree.repo, worktree.path
    # As bytes: a text pipe would turn the patch's \n into \r\n on Windows
    patch = subprocess.run(
        ["git", "diff", "--binary", "HEAD"], cwd=repo, capture_output=True, check=True
    ).stdout
    if patch.strip():
        applied = subprocess.run(
            ["git", "apply", "--whitespace=nowarn"], cwd=path, input=patch, capture_output=True
        )
        if applied.returncode != 0:
            raise WorktreeError(applied.stderr.decode("utf-8", "replace").strip()[:300])
    untracked = _git(repo, "ls-files", "--others", "--exclude-standard", "-z").split("\0")
    for name in filter(None, untracked):
        source = repo / name
        if source.is_file() and source.stat().st_size <= MAX_UNTRACKED_BYTES:
            target = path / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
    if not (patch.strip() or any(untracked)):
        return
    _git(path, "add", "-A")
    if not _git(path, "diff", "--cached", "--name-only").strip():
        return
    _git(
        path,
        *_identity(path),
        "commit",
        "-q",
        "--no-verify",
        "-m",
        "Uncommitted changes (copied for the sub-agent)",
    )
    worktree.base = _git(path, "rev-parse", "HEAD").strip()
    worktree.seeded = True


def _identity(cwd: Path) -> List[str]:
    if _git(cwd, "config", "user.email", check=False).strip():
        return []
    return ["-c", "user.name=Joshu", "-c", "user.email=joshu@localhost"]


def commit(worktree: Worktree, message: str) -> List[str]:
    """Commit everything the sub-agent changed; the changed files (none: nothing committed)."""
    _git(worktree.path, "add", "-A")
    changed = _git(worktree.path, "diff", "--cached", "--name-only").split()
    if not changed:
        return []
    _git(worktree.path, *_identity(worktree.path), "commit", "-q", "--no-verify", "-m", message)
    return changed


def finish(
    worktree: Worktree,
    message: str,
    apply: bool = True,
    before_apply: Optional[Callable[[List[Path]], None]] = None,
) -> Outcome:
    """
    Commit the work, apply it to the working tree when that is safe, and
    remove the worktree (the branch too, once applied). `before_apply` gets
    the files about to change (for checkpoints).
    """
    outcome = Outcome()
    try:
        outcome.files = commit(worktree, message)
        if not outcome.files:
            outcome.message = "The sub-agent changed no files."
            return outcome
        outcome.stat = _git(worktree.repo, "diff", "--stat", worktree.base, worktree.branch).strip()
        if not apply:
            outcome.branch = worktree.branch
            outcome.message = f"Its changes are on branch {worktree.branch}."
            return outcome
        return apply_work(worktree, outcome, before_apply)
    finally:
        remove(worktree, delete_branch=outcome.applied or not outcome.files)


def apply_work(
    worktree: Worktree,
    outcome: Outcome,
    before_apply: Optional[Callable[[List[Path]], None]] = None,
) -> Outcome:
    """
    Apply the work on `worktree.branch` (since `worktree.base`) to the working
    tree, or keep it on the branch and say why. Needs only the repository and
    the branch: the worktree directory may be gone (a finished job).
    """
    with _apply_lock:
        # Seeded: the patch is relative to the uncommitted changes, so it applies
        # over them (and fails cleanly if they changed meanwhile)
        busy = (
            ""
            if worktree.seeded
            else _git(worktree.repo, "status", "--porcelain", "--", *outcome.files).strip()
        )
        if busy:
            outcome.branch = worktree.branch
            outcome.message = (
                f"Not applied: these files have uncommitted changes in the working tree:\n{busy}\n"
                f"The changes are on branch {worktree.branch} (git merge {worktree.branch})."
            )
            return outcome
        if before_apply is not None:
            before_apply([worktree.repo / name for name in outcome.files])
        # As bytes: a text pipe would turn the patch's \n into \r\n on Windows
        patch = subprocess.run(
            ["git", "diff", "--binary", worktree.base, worktree.branch],
            cwd=worktree.repo,
            capture_output=True,
            check=True,
        ).stdout
        applied = subprocess.run(
            ["git", "apply", "--whitespace=nowarn"]
            if worktree.seeded
            else ["git", "apply", "--3way", "--whitespace=nowarn"],
            cwd=worktree.repo,
            input=patch,
            capture_output=True,
        )
        result = subprocess.CompletedProcess(
            applied.args,
            applied.returncode,
            applied.stdout.decode("utf-8", "replace"),
            applied.stderr.decode("utf-8", "replace"),
        )
        if result.returncode != 0:
            outcome.branch = worktree.branch
            outcome.message = (
                f"Not applied: {(result.stderr or result.stdout).strip()[:300]}\n"
                f"The changes are on branch {worktree.branch} (git merge {worktree.branch})."
            )
            return outcome
        # --3way stages what it applies; leave it unstaged like any other edit
        _git(worktree.repo, "reset", "-q", "--", *outcome.files, check=False)
    outcome.applied = True
    outcome.message = "Applied to the working tree (not committed)."
    return outcome


def remove(worktree: Worktree, delete_branch: bool) -> None:
    _git(worktree.repo, "worktree", "remove", "--force", str(worktree.path), check=False)
    if worktree.path.exists():
        shutil.rmtree(worktree.path, ignore_errors=True)
        _git(worktree.repo, "worktree", "prune", check=False)
    if delete_branch:
        _git(worktree.repo, "branch", "-q", "-D", worktree.branch, check=False)
