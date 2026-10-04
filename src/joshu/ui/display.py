from __future__ import annotations

from pathlib import Path
from typing import Optional

from rich.console import Console, Group
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from joshu.ui.theme import GLYPH, MASCOT, current_theme, style

console = Console()


def mascot(color: Optional[str] = None) -> Text:
    """Joshu's mascot, in the theme's mascot color."""
    theme = current_theme()
    return Text("\n".join(MASCOT), style=style(color if color is not None else theme.mascot))


def print_banner(model_name: Optional[str] = None, cwd: Optional[Path] = None) -> None:
    """Welcome box: mascot, version, working directory and model, plus first-run tips."""
    from joshu import __version__

    theme = current_theme()
    cwd = cwd or Path.cwd()
    model, provider = _model_and_provider(model_name)

    info = [
        Text.assemble(
            (f"{GLYPH} ", style(theme.accent)),
            ("Welcome to Joshu", "bold"),
            (f"  v{__version__}", style(theme.dim)),
        ),
        Text("/help for commands · ? for shortcuts · shift+tab to switch mode", style(theme.dim)),
        Text(""),
        Text.assemble(("cwd    ", style(theme.dim)), str(cwd)),
    ]
    if model:
        info.append(
            Text.assemble(("model  ", style(theme.dim)), model, (f"  {provider}", style(theme.dim)))
        )

    layout = Table.grid(padding=(0, 2))
    layout.add_column(no_wrap=True)
    layout.add_column()
    layout.add_row(mascot(), Group(*info))
    console.print(Panel(layout, border_style=style(theme.accent), expand=False, padding=(0, 2)))

    if not _has_instructions(cwd):
        tips = [
            "Run /init to create an AGENTS.md with instructions for Joshu",
            "Ask about your code, or ask Joshu to change it",
            "Press Esc to interrupt, /rewind to undo a request",
        ]
        console.print(Text(" Tips for getting started:", style(theme.dim)))
        for number, tip in enumerate(tips, 1):
            console.print(Text(f"  {number}. {tip}", style(theme.dim)))
    console.print()


def _model_and_provider(model_name: Optional[str]) -> tuple:
    try:
        from joshu.core.config import get_config_manager
        from joshu.core.providers import DEFAULT_PROVIDER

        config = get_config_manager()
        provider = config.get("provider") or DEFAULT_PROVIDER
        return model_name or config.get("model") or "", provider
    except Exception:
        return model_name or "", ""


def _has_instructions(cwd: Path) -> bool:
    try:
        from joshu.core.instructions import instruction_files

        return bool(instruction_files(cwd))
    except Exception:
        return True
