"""
Instruction files the agent follows.

Read into the system prompt, in this order (later ones are more specific):

    ~/.joshu/AGENTS.md              your instructions for every project
    AGENTS.md, JOSHU.md             in each directory from the repository root
                                    down to the working directory
    config/JOSHU.md                 at the repository root (older location)

The repository root is the nearest directory above the working directory that
contains `.git`; without one, only the working directory is searched.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import List, Optional

from joshu.core.paths import joshu_home

logger = logging.getLogger(__name__)

INSTRUCTION_FILES = ("AGENTS.md", "JOSHU.md")
LEGACY_FILE = Path("config") / "JOSHU.md"
MAX_TOTAL_CHARS = 40_000


def find_repo_root(start: Path) -> Optional[Path]:
    """The nearest directory at or above `start` that contains .git."""
    start = start.resolve()
    for directory in [start, *start.parents]:
        if (directory / ".git").exists():
            return directory
    return None


def instruction_files(cwd: Optional[Path] = None) -> List[Path]:
    """Instruction files that apply in `cwd`, least specific first."""
    cwd = (cwd or Path.cwd()).resolve()
    files: List[Path] = []

    user_file = joshu_home() / "AGENTS.md"
    if user_file.is_file():
        files.append(user_file)

    root = find_repo_root(cwd) or cwd
    try:
        relative = cwd.relative_to(root)
    except ValueError:
        relative = Path()
    directories = [root]
    for part in relative.parts:
        directories.append(directories[-1] / part)

    legacy = root / LEGACY_FILE
    if legacy.is_file():
        files.append(legacy)

    for directory in directories:
        for name in INSTRUCTION_FILES:
            candidate = directory / name
            if candidate.is_file() and candidate not in files:
                files.append(candidate)
    return files


def load_instructions(cwd: Optional[Path] = None) -> str:
    """The text of all applicable instruction files, each under its path."""
    cwd = (cwd or Path.cwd()).resolve()
    sections: List[str] = []
    total = 0
    for path in instruction_files(cwd):
        try:
            text = path.read_text(encoding="utf-8").strip()
        except OSError as e:
            logger.warning(f"Could not read {path}: {e}")
            continue
        if not text:
            continue
        if total + len(text) > MAX_TOTAL_CHARS:
            text = text[: max(0, MAX_TOTAL_CHARS - total)] + "\n... (truncated)"
        sections.append(f"From {_display(path, cwd)}:\n{text}")
        total += len(text)
        if total >= MAX_TOTAL_CHARS:
            break
    return "\n\n".join(sections)


def _display(path: Path, cwd: Path) -> str:
    try:
        return str(path.relative_to(cwd))
    except ValueError:
        home = joshu_home()
        try:
            return f"~/.joshu/{path.relative_to(home)}"
        except ValueError:
            return str(path)
