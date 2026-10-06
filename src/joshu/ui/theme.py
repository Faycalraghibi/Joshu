"""
Joshu's look: color themes, the mascot and the glyphs used on screen.

The theme comes from the `theme` setting (`/theme` in interactive mode or
`joshu config --set theme=light`). Colors are hex values usable by both rich
and prompt_toolkit; the `plain` theme uses no color at all.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional


@dataclass(frozen=True)
class Theme:
    name: str
    label: str
    accent: str  # brand color: bullets, borders, spinner
    mascot: str
    secondary: str
    dim: str
    rule: str
    success: str
    error: str
    warning: str
    edits: str  # accept-edits mode
    plan: str  # plan mode
    bypass: str  # bypass mode
    diff_add: str
    diff_remove: str
    diff_add_bg: str = ""  # background of added / removed diff lines
    diff_remove_bg: str = ""


THEMES: Dict[str, Theme] = {
    "dark": Theme(
        name="dark",
        label="Dark (default)",
        accent="#7aa2f7",
        mascot="#7aa2f7",
        secondary="#bb9af7",
        dim="#7f849c",
        rule="#3b4261",
        success="#9ece6a",
        error="#f7768e",
        warning="#e0af68",
        edits="#bb9af7",
        plan="#7dcfff",
        bypass="#f7768e",
        diff_add="#9ece6a",
        diff_remove="#f7768e",
        diff_add_bg="#1d3320",
        diff_remove_bg="#3d1d24",
    ),
    "light": Theme(
        name="light",
        label="Light",
        accent="#2e5fd1",
        mascot="#2e5fd1",
        secondary="#7b3fbf",
        dim="#6b7280",
        rule="#c0c4cc",
        success="#2e7d32",
        error="#c62828",
        warning="#b26a00",
        edits="#7b3fbf",
        plan="#00838f",
        bypass="#c62828",
        diff_add="#2e7d32",
        diff_remove="#c62828",
        diff_add_bg="#dcf5e0",
        diff_remove_bg="#fde4e4",
    ),
    "colorblind": Theme(
        name="colorblind",
        label="Color-blind friendly (blue / orange diffs)",
        accent="#56b4e9",
        mascot="#56b4e9",
        secondary="#cc79a7",
        dim="#8a8a8a",
        rule="#4a4a4a",
        success="#56b4e9",
        error="#e69f00",
        warning="#f0e442",
        edits="#cc79a7",
        plan="#009e73",
        bypass="#e69f00",
        diff_add="#56b4e9",
        diff_remove="#e69f00",
        diff_add_bg="#10303f",
        diff_remove_bg="#3a2a05",
    ),
    "plain": Theme(
        name="plain",
        label="Plain (no colors)",
        accent="",
        mascot="",
        secondary="",
        dim="",
        rule="",
        success="",
        error="",
        warning="",
        edits="",
        plan="",
        bypass="",
        diff_add="",
        diff_remove="",
    ),
}

DEFAULT_THEME = "dark"

# The mark next to Joshu's name and in the working indicator
GLYPH = "✦"
# Working indicator frames (a twinkling star)
SPINNER_FRAMES = ["·", "✧", "✦", "✶", "✦", "✧"]

# Joshu's mascot: a small helper bot with a spark on its antenna
MASCOT: List[str] = [
    "   ✦   ",
    " ╭─┴─╮ ",
    " │•‿•│ ",
    " ╰───╯ ",
]


def current_theme(name: Optional[str] = None) -> Theme:
    """The configured theme (or `name`), falling back to the default."""
    if name is None:
        try:
            from joshu.core.config import get_config_manager

            name = str(get_config_manager().get("theme") or DEFAULT_THEME)
        except Exception:
            name = DEFAULT_THEME
    return THEMES.get(name, THEMES[DEFAULT_THEME])


def style(color: str, *extra: str) -> str:
    """Rich markup style from a theme color plus modifiers (bold, ...)."""
    parts = [*extra, color] if color else list(extra)
    return " ".join(parts) or "default"
