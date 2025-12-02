"""Auto-completion for interactive mode."""

from pathlib import Path
from typing import List

try:
    from prompt_toolkit.completion import PathCompleter, WordCompleter

    PROMPT_TOOLKIT_AVAILABLE = True
except ImportError:
    PathCompleter = None
    WordCompleter = None
    PROMPT_TOOLKIT_AVAILABLE = False


def get_path_completer():
    """Get path completer for file paths."""
    if not PROMPT_TOOLKIT_AVAILABLE:
        return None
    return PathCompleter()


def get_command_completer():
    """Get command completer for common commands."""
    if not PROMPT_TOOLKIT_AVAILABLE:
        return None
    return WordCompleter(
        [
            "ls",
            "cd",
            "pwd",
            "find",
            "grep",
            "cat",
            "less",
            "head",
            "tail",
            "cp",
            "mv",
            "rm",
            "mkdir",
            "rmdir",
            "chmod",
            "chown",
            "git",
            "docker",
            "pip",
            "npm",
            "yarn",
            "python",
            "node",
        ],
        ignore_case=True,
    )


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
