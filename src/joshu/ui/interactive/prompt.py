"""The input area: prompt line, rules around it and the hint line below."""

from __future__ import annotations

import shutil
from typing import List, Tuple

try:
    from prompt_toolkit.styles import Style

    PROMPT_TOOLKIT_AVAILABLE = True
except ImportError:
    Style = None
    PROMPT_TOOLKIT_AVAILABLE = False

ACCENT = "#d97757"

FormattedText = List[Tuple[str, str]]

# Mode name -> (hint shown under the input, style class)
MODE_HINTS = {
    "default": ("? for shortcuts", "class:hint"),
    "accept_edits": ("⏵⏵ accept edits on (shift+tab to cycle)", "class:mode-edits"),
    "plan": ("⏸ plan mode on (shift+tab to cycle)", "class:mode-plan"),
    "bypass": ("⏵⏵ bypass permissions on (shift+tab to cycle)", "class:mode-bypass"),
    "ask": ("ask mode: answers without tools (shift+tab for agent mode)", "class:mode-plan"),
}

SHORTCUTS = """\
  !  run a shell command        /  commands           @  attach a file or image
  esc  interrupt the agent      shift+tab  cycle modes (default, accept edits, plan)
  tab  complete commands        ctrl+r  search history
  ctrl+c  clear input (twice on an empty prompt to exit)    ctrl+d  exit"""


def get_style():
    """prompt_toolkit styles for the input area."""
    if not PROMPT_TOOLKIT_AVAILABLE:
        return None
    return Style.from_dict(
        {
            "prompt": "bold",
            "rule": "#555555",
            "hint": "#888888",
            "model": "#888888",
            "notice": "#d7af00",
            "mode-edits": "#af87ff",
            "mode-plan": "#5fafaf",
            "mode-bypass": "#ff5f5f",
            "placeholder": "#666666 italic",
            "bottom-toolbar": "noreverse",
            "normal-mode": "#5f87ff bold",
        }
    )


def _rule() -> str:
    return "─" * max(10, shutil.get_terminal_size((80, 24)).columns - 1)


def prompt_message(vim_normal: bool = False, multiline: bool = False) -> FormattedText:
    """Top rule, then the `>` prompt."""
    marker = "N " if vim_normal else ("… " if multiline else "> ")
    style = "class:normal-mode" if vim_normal else "class:prompt"
    return [("class:rule", _rule() + "\n"), (style, marker)]


def bottom_toolbar(mode: str, model: str = "", notice: str = "") -> FormattedText:
    """Bottom rule, then the mode hint on the left and the model on the right."""
    hint, style = MODE_HINTS.get(mode, MODE_HINTS["default"])
    if notice:
        hint, style = notice, "class:notice"
    width = max(10, shutil.get_terminal_size((80, 24)).columns - 1)
    left = "  " + hint
    room = max(0, width - len(left) - 2)
    right = model if len(model) <= room else (model[: room - 1] + "…" if room > 1 else "")
    gap = " " * max(1, width - len(left) - len(right))
    return [
        ("class:rule", _rule() + "\n"),
        (style, left),
        ("", gap),
        ("class:model", right),
    ]


PLACEHOLDER = 'Try "explain this codebase" or "fix the failing test"'
