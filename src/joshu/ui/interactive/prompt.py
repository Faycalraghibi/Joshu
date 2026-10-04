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
  alt+enter or \\+enter  new line          alt+v  paste an image
  esc  interrupt the agent      shift+tab  cycle modes (default, accept edits, plan)
  tab  complete commands        ctrl+r  search history        ctrl+g  edit in $EDITOR
  ctrl+o  full tool output      ctrl+l  clear the screen
  ctrl+c  clear input (twice on an empty prompt to exit)
  ctrl+d  exit"""


def get_style():
    """prompt_toolkit styles for the input area, from the current theme."""
    if not PROMPT_TOOLKIT_AVAILABLE:
        return None
    from joshu.ui.theme import current_theme

    theme = current_theme()

    def color(value: str, extra: str = "") -> str:
        return " ".join(part for part in (value, extra) if part)

    return Style.from_dict(
        {
            "prompt": color(theme.accent, "bold"),
            "rule": color(theme.rule),
            "hint": color(theme.dim),
            "model": color(theme.dim),
            "notice": color(theme.warning),
            "mode-edits": color(theme.edits),
            "mode-plan": color(theme.plan),
            "mode-bypass": color(theme.bypass),
            "placeholder": color(theme.dim, "italic"),
            "bottom-toolbar": "noreverse",
            "normal-mode": color(theme.secondary, "bold"),
            "completion-menu": "bg:#1f2335 #c0caf5" if theme.name == "dark" else "",
            "completion-menu.completion.current": color(theme.accent, "reverse"),
            "completion-menu.meta.completion": color(theme.dim),
        }
    )


def _rule() -> str:
    return "─" * max(10, shutil.get_terminal_size((80, 24)).columns - 1)


def prompt_message(vim_normal: bool = False, multiline: bool = False) -> FormattedText:
    """Top rule, then the `>` prompt."""
    marker = "N " if vim_normal else ("… " if multiline else "> ")
    style = "class:normal-mode" if vim_normal else "class:prompt"
    return [("class:rule", _rule() + "\n"), (style, marker)]


def bottom_toolbar(
    mode: str, model: str = "", notice: str = "", status: str = "", activity: str = ""
) -> FormattedText:
    """
    Bottom rule, then the mode hint and `activity` (todo progress, background
    shells) on the left and the status line (or model) on the right.
    """
    hint, style = MODE_HINTS.get(mode, MODE_HINTS["default"])
    if notice:
        hint, style = notice, "class:notice"
    width = max(10, shutil.get_terminal_size((80, 24)).columns - 1)
    left = "  " + hint
    extra = f"  ·  {activity}" if activity else ""
    room = max(0, width - len(left) - 2)
    extra = extra if len(extra) <= room // 2 else extra[: max(0, room // 2 - 1)] + "…"
    room = max(0, room - len(extra))
    model = status or model
    right = model if len(model) <= room else (model[: room - 1] + "…" if room > 1 else "")
    gap = " " * max(1, width - len(left) - len(extra) - len(right))
    return [
        ("class:rule", _rule() + "\n"),
        (style, left),
        ("class:hint", extra),
        ("", gap),
        ("class:model", right),
    ]


PLACEHOLDER = 'Try "explain this codebase" or "fix the failing test"'
