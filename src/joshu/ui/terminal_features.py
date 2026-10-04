"""
What the terminal Joshu runs in can do beyond plain text: desktop
notifications and a progress indicator (taskbar / tab), both through OSC
escape sequences that other terminals ignore.
"""

from __future__ import annotations

import os
from typing import Mapping, Optional

# Terminals that turn OSC 9 into a desktop notification
_OSC9_NOTIFY = {"iTerm.app", "WezTerm", "ghostty"}


def _program(env: Mapping[str, str]) -> str:
    return env.get("TERM_PROGRAM", "")


def notification_sequence(message: str, env: Optional[Mapping[str, str]] = None) -> str:
    """Escape sequence that shows `message` as a desktop notification, or "" if unsupported."""
    env = os.environ if env is None else env
    message = " ".join(message.split()).replace("\x07", "").replace("\x1b", "")
    if env.get("KITTY_WINDOW_ID"):
        return f"\x1b]99;;{message}\x1b\\"
    if _program(env) in _OSC9_NOTIFY:
        return f"\x1b]9;{message}\x07"
    return ""


def supports_progress(env: Optional[Mapping[str, str]] = None) -> bool:
    """True in terminals that show OSC 9;4 progress (Windows Terminal, ConEmu, Ghostty, WezTerm)."""
    env = os.environ if env is None else env
    return bool(
        env.get("WT_SESSION") or env.get("ConEmuPID") or _program(env) in ("ghostty", "WezTerm")
    )


PROGRESS_BUSY = "\x1b]9;4;3;0\x07"  # indeterminate
PROGRESS_CLEAR = "\x1b]9;4;0;0\x07"
