"""Basic interactive mode (fallback when prompt_toolkit is not available)."""

from typing import Optional

import typer
from rich.console import Console

from joshu.core.context_provider import ContextProvider
from joshu.core.safety import assess_command_safety
from joshu.core.translate import translate_to_command
from joshu.tools.shell import run_command

from .translation_helpers import check_conversational_response, display_safety_report

console = Console()


def start_basic_interactive_mode(
    model: str, sandbox: bool, config_manager, context_provider: Optional[ContextProvider] = None
) -> None:
    """Start basic interactive chat mode (backward compatibility)."""

    auto_execute = config_manager.get("auto_execute", False)

    mode_text = " (sandbox mode)" if sandbox else ""
    console.print(f"[bold green]Interactive mode starting...{mode_text}[/bold green]")
    console.print("[dim]Type 'exit' or 'quit' to leave interactive mode.[/dim]\n")

    while True:
        try:
            user_input = console.input("[bold blue]You:[/bold blue] ").strip()
            if user_input.lower() in ["exit", "quit"]:
                console.print("[dim]Goodbye![/dim]")
                break

            if not user_input:
                continue

            console.print(f"[bold]Prompt:[/bold] {user_input}")

            translation = translate_to_command(user_input, context_provider, model)

            if not translation:
                console.print("[yellow]No translation found. Try rephrasing.[/yellow]")
                continue

            console.print(f"[bold]Proposed command:[/bold] [cyan]{translation.command}[/cyan]")
            console.print(f"[dim]{translation.explanation}[/dim]\n")

            # Check if conversational response
            if check_conversational_response(translation):
                code, out, err = run_command(translation.command)
                if code == 0:
                    if out:
                        console.print(out)
                else:
                    if err:
                        console.print(f"[red]{err}[/red]")
                continue

            report = assess_command_safety(translation.command, sandbox)

            if not report.safe:
                display_safety_report(report)
                continue

            if auto_execute:
                console.print("[dim]Auto-executing command (auto_execute enabled in config)[/dim]")
                proceed = True
            else:
                proceed = typer.confirm("Execute this command?", default=False)

            if not proceed:
                console.print("[dim]Cancelled.[/dim]\n")
                if context_provider:
                    context_provider.update_context_from_response(
                        user_input, "Command cancelled by user"
                    )
                continue

            code, out, err = run_command(translation.command)
            if code == 0:
                if out:
                    console.print(out)
                console.print("[green]Done.[/green]")

                if context_provider:
                    context_provider.update_context_from_response(
                        user_input, f"Executed: {translation.command}\nOutput: {out[:100]}..."
                    )
            else:
                if err:
                    console.print(f"[red]{err}[/red]")

                if context_provider:
                    context_provider.update_context_from_response(
                        user_input,
                        f"Failed to execute: {translation.command}\nError: {err[:100]}...",
                    )

            console.print()

        except KeyboardInterrupt:
            console.print("\n[dim]Goodbye![/dim]")
            break
        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")
