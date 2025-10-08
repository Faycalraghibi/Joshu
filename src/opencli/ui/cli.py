from __future__ import annotations

import os
from typing import Optional

import typer
from rich.console import Console
from dotenv import load_dotenv

from .display import print_banner
from opencli.core.translate import translate_to_command
from opencli.core.safety import assess_command_safety
from opencli.tools.shell import run_command


app = typer.Typer(add_completion=True, no_args_is_help=True)
console = Console()


def version_callback(value: bool) -> None:
    if value:
        # Lazy import to avoid import-time side effects
        from opencli import __version__

        console.print(f"OpenCLI Assistant v{__version__}")
        raise typer.Exit()


@app.callback()
def main_callback(
    version: Optional[bool] = typer.Option(
        None,
        "--version",
        callback=version_callback,
        is_eager=True,
        help="Show version and exit.",
    ),
    model: str = typer.Option(
        os.getenv("OPENCLI_MODEL", "llama-3-8b"),
        "--model",
        "-m",
        help="LLM model to use (see config/models.yaml)",
        show_default=True,
    ),
) -> None:
    """OpenCLI Assistant - Natural language meets your terminal."""
    load_dotenv()
    print_banner(model)


@app.command()
def run(
    prompt: str = typer.Argument(..., help="Instruction or task to execute."),
    interactive: bool = typer.Option(
        False, "--interactive", "-i", help="Start interactive chat mode."
    ),
    yes: bool = typer.Option(False, "--yes", "-y", help="Execute without confirmation if safe."),
) -> None:
    """Execute a one-off prompt or start interactive mode."""
    if interactive:
        console.print("[bold green]Interactive mode coming soon.[/bold green]")
        return

    console.print(f"[bold]Prompt:[/bold] {prompt}")
    translation = translate_to_command(prompt)
    if not translation:
        console.print("[yellow]No direct translation found. Try rephrasing.[/yellow]")
        raise typer.Exit(code=2)

    console.print(f"[bold]Proposed command:[/bold] [cyan]{translation.command}[/cyan]")
    console.print(f"[dim]{translation.explanation}[/dim]\n")
    report = assess_command_safety(translation.command)
    if not report.safe:
        console.print("[red]Command flagged as risky:[/red]")
        for r in report.reasons:
            console.print(f" - {r}")
        if report.suggested_alternative:
            console.print(
                f"[yellow]Suggested safer alternative:[/yellow] {report.suggested_alternative}"
            )
        raise typer.Exit(code=3)

    proceed = yes or typer.confirm("Execute this command?", default=False)
    if not proceed:
        console.print("[dim]Cancelled.[/dim]\n")
        raise typer.Exit()

    code, out, err = run_command(translation.command)
    if code == 0:
        if out:
            console.print(out)
        console.print("[green]Done.[/green]")
    else:
        if err:
            console.print(f"[red]{err}[/red]")
        raise typer.Exit(code=code)


def main() -> None:
    app()


if __name__ == "__main__":
    main()


