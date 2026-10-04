"""Auto-completion for interactive mode: slash commands and @file references."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple, Union

try:
    from prompt_toolkit.completion import Completer, Completion, PathCompleter

    PROMPT_TOOLKIT_AVAILABLE = True
except ImportError:
    PathCompleter = None
    Completer = object  # type: ignore[assignment,misc]
    Completion = None
    PROMPT_TOOLKIT_AVAILABLE = False

# Directories never offered for @ completion
SKIP_DIRS = {
    ".git",
    "node_modules",
    "__pycache__",
    ".venv",
    "venv",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    "dist",
    "build",
    ".idea",
    ".vscode",
}
MAX_FILES = 5000
MAX_SUGGESTIONS = 30


def get_path_completer():
    """Get path completer for file paths."""
    if not PROMPT_TOOLKIT_AVAILABLE:
        return None
    return PathCompleter()


def get_command_completer(extra: Optional[Iterable[Union[str, Tuple[str, str]]]] = None):
    """
    Completer for slash commands (built-in ones plus `extra`: custom commands
    and skills, as "/name" or ("/name", description)) and @file references.
    """
    if not PROMPT_TOOLKIT_AVAILABLE:
        return None
    from joshu.ui.interactive.command_registry import COMMANDS

    entries: Dict[str, Tuple[str, str]] = {}
    for command in COMMANDS:
        entries[command.name] = (command.usage, command.description)
        for alias in command.aliases:
            entries.setdefault(alias, (f"/{alias}", f"same as /{command.name}"))
    for item in extra or []:
        name, description = item if isinstance(item, tuple) else (item, "")
        entries.setdefault(
            name.lstrip("/"), (name if name.startswith("/") else f"/{name}", description)
        )
    return JoshuCompleter(entries)


class JoshuCompleter(Completer):
    """`/` at the start of the input completes commands; `@` completes file paths."""

    def __init__(self, entries: Dict[str, Tuple[str, str]], root: Optional[Path] = None) -> None:
        self.entries = entries
        self.root = root
        self._files: Optional[List[str]] = None

    @property
    def commands(self) -> List[str]:
        return sorted(f"/{name}" for name in self.entries)

    def get_completions(self, document, complete_event):
        text = document.text_before_cursor
        if text.startswith("/") and " " not in text:
            typed = text[1:].lower()
            for name in sorted(self.entries):
                if name.startswith(typed):
                    usage, description = self.entries[name]
                    yield Completion(
                        f"/{name}",
                        start_position=-len(text),
                        display=usage,
                        display_meta=description,
                    )
            return

        word = text.split()[-1] if text and not text.endswith(" ") else ""
        if word.startswith("@"):
            query = word[1:].replace("\\", "/").lower()
            for path in self._match_files(query):
                yield Completion("@" + path, start_position=-len(word), display=path)

    def _match_files(self, query: str) -> List[str]:
        files = self._list_files()
        if not query:
            return files[:MAX_SUGGESTIONS]
        starts = [f for f in files if f.lower().startswith(query)]
        names = [f for f in files if f not in starts and Path(f).name.lower().startswith(query)]
        contains = [f for f in files if f not in starts and f not in names and query in f.lower()]
        return (starts + names + contains)[:MAX_SUGGESTIONS]

    def _list_files(self) -> List[str]:
        if self._files is None:
            self._files = list_project_files(self.root or Path.cwd())
        return self._files


def list_project_files(root: Path, limit: int = MAX_FILES) -> List[str]:
    """Relative paths of files under `root` (POSIX separators), skipping build/VCS dirs."""
    found: List[str] = []
    for directory, dirs, files in os.walk(root):
        dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS and not d.startswith("."))
        base = Path(directory).relative_to(root)
        for name in sorted(files):
            found.append((base / name).as_posix())
            if len(found) >= limit:
                return found
    return found


def get_file_completions(text: str) -> List[str]:
    """Get file completions for @ prefix."""
    if not text.startswith("@"):
        return []

    path_text = text[1:]
    path = Path(path_text)

    if not path.is_absolute():
        path = Path.cwd() / path

    if path.is_dir():
        return [str(p) for p in path.iterdir()]
    else:
        parent = path.parent
        if parent.exists():
            prefix = path.name
            return [str(p) for p in parent.iterdir() if p.name.startswith(prefix)]

    return []
