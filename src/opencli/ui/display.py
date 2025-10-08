from __future__ import annotations

from rich.panel import Panel
from rich.console import Console


console = Console()


def print_banner(model_name: str) -> None:
    banner = Panel.fit(
        f"OpenCLI Assistant\nModel: [bold]{model_name}[/bold]",
        title="🤖 OpenCLI",
        subtitle="Democratizing AI assistance, one command at a time",
    )
    console.print(banner)


