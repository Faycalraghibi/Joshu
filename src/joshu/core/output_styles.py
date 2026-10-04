"""
Output styles: how the agent writes its replies (the `output_style` setting).

Built-in styles are below. Custom ones are Markdown files in
`.joshu/output-styles/` or `~/.joshu/output-styles/`: the first line starting
with `description:` (optional) describes it, the rest is added to the system
prompt.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional


@dataclass(frozen=True)
class OutputStyle:
    name: str
    description: str
    instructions: str  # added to the system prompt ("" for the default)


BUILTIN_STYLES: Dict[str, OutputStyle] = {
    "default": OutputStyle("default", "Balanced: get the task done, explain briefly", ""),
    "concise": OutputStyle(
        "concise",
        "Minimal text: results first, no preamble",
        "Output style: concise. Keep replies as short as possible: lead with the result, "
        "skip preambles and recaps, use fragments where clear. Explain only when asked or "
        "when something is surprising or risky.",
    ),
    "explanatory": OutputStyle(
        "explanatory",
        "Explains the reasoning and trade-offs behind each change",
        "Output style: explanatory. While working, explain why you make each important "
        "choice: the trade-offs, the alternatives you rejected and how the code you touch "
        "fits into the codebase. Add short 'Insight' notes about patterns worth knowing.",
    ),
    "learning": OutputStyle(
        "learning",
        "Teaches as it goes and leaves small parts for you to write",
        "Output style: learning. The user wants to learn. Explain concepts as you go, and "
        "for small, instructive pieces of code (a few lines), don't write them yourself: "
        "mark the spot with a TODO, explain what's needed and ask the user to write it, "
        "then review what they wrote.",
    ),
}

DEFAULT_STYLE = "default"


def style_dirs(cwd: Optional[Path] = None) -> list:
    from joshu.core.paths import joshu_home

    cwd = cwd or Path.cwd()
    return [cwd / ".joshu" / "output-styles", joshu_home() / "output-styles"]


def available_styles(cwd: Optional[Path] = None) -> Dict[str, OutputStyle]:
    """Built-in styles plus custom ones (a custom style can't replace a built-in)."""
    styles = dict(BUILTIN_STYLES)
    for directory in style_dirs(cwd):
        if not directory.is_dir():
            continue
        for path in sorted(directory.glob("*.md")):
            name = path.stem.lower()
            if name in styles:
                continue
            try:
                text = path.read_text(encoding="utf-8").strip()
            except OSError:
                continue
            description = "custom style"
            first, _, rest = text.partition("\n")
            if first.lower().startswith("description:"):
                description = first.split(":", 1)[1].strip() or description
                text = rest.strip()
            styles[name] = OutputStyle(name, description, text)
    return styles


def style_instructions(name: Optional[str], cwd: Optional[Path] = None) -> str:
    """System prompt text for the style called `name` ("" for default or unknown)."""
    if not name or name == DEFAULT_STYLE:
        return ""
    style = available_styles(cwd).get(name)
    return style.instructions if style else ""
