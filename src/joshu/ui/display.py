from __future__ import annotations

from pathlib import Path
from typing import Optional

from rich.console import Console, Group
from rich.panel import Panel
from rich.text import Text

console = Console()

ACCENT = "#d97757"


def print_banner(model_name: Optional[str] = None, cwd: Optional[Path] = None) -> None:
    """Welcome box: version, working directory and model, plus first-run tips."""
    from joshu import __version__

    cwd = cwd or Path.cwd()
    model, provider = _model_and_provider(model_name)

    lines = [
        Text.assemble(("✻ ", ACCENT), ("Welcome to Joshu", "bold"), (f"  v{__version__}", "dim")),
        Text(""),
        Text("  /help for help · ? for shortcuts · shift+tab to switch mode", style="dim"),
        Text(""),
        Text.assemble(("  cwd: ", "dim"), str(cwd)),
    ]
    if model:
        lines.append(Text.assemble(("  model: ", "dim"), model, (f" ({provider})", "dim")))
    console.print(Panel(Group(*lines), border_style=ACCENT, expand=False, padding=(0, 1)))

    if not _has_instructions(cwd):
        console.print(
            Text.assemble(
                (" Tips for getting started:\n", "dim"),
                ("  1. Run /init to create an AGENTS.md with instructions for Joshu\n", "dim"),
                ("  2. Ask questions about your code, or ask Joshu to change it\n", "dim"),
                ("  3. Press Esc to interrupt, and /rewind to undo a request", "dim"),
            )
        )
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
