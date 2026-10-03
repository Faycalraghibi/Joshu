"""Auto-completion for interactive mode."""

from pathlib import Path
from typing import Iterable, List, Optional

try:
    from prompt_toolkit.completion import Completer, Completion, PathCompleter

    PROMPT_TOOLKIT_AVAILABLE = True
except ImportError:
    PathCompleter = None
    Completer = None
    Completion = None
    PROMPT_TOOLKIT_AVAILABLE = False


def get_path_completer():
    """Get path completer for file paths."""
    if not PROMPT_TOOLKIT_AVAILABLE:
        return None
    return PathCompleter()


SLASH_COMMANDS = [
    "/agent",
    "/agents",
    "/ask",
    "/clear",
    "/commands",
    "/compact",
    "/config",
    "/cost",
    "/help",
    "/history",
    "/init",
    "/memory",
    "/model",
    "/models",
    "/permissions",
    "/plan",
    "/reset",
    "/resume",
    "/rewind",
    "/search",
    "/session",
    "/undo",
]


def get_command_completer(extra: Optional[Iterable[str]] = None):
    """Complete slash commands (built-in ones plus `extra`, e.g. custom commands)."""
    if not PROMPT_TOOLKIT_AVAILABLE:
        return None
    return SlashCommandCompleter(sorted(set(SLASH_COMMANDS) | set(extra or [])))


if PROMPT_TOOLKIT_AVAILABLE:

    class SlashCommandCompleter(Completer):
        """Completes the command name when the input starts with `/`."""

        def __init__(self, commands: List[str]) -> None:
            self.commands = commands

        def get_completions(self, document, complete_event):
            text = document.text_before_cursor
            if not text.startswith("/") or " " in text:
                return
            for command in self.commands:
                if command.startswith(text.lower()):
                    yield Completion(command, start_position=-len(text))


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
