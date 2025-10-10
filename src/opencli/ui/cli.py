from __future__ import annotations

import os
import sys
import logging
from typing import Optional

import typer
from rich.console import Console
from dotenv import load_dotenv

from .display import print_banner
from opencli.core.translate import translate_to_command
from opencli.core.safety import assess_command_safety
from opencli.tools.shell import run_command
from opencli.core.context import ConversationContext
from opencli.core.context_provider import ContextProvider

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = typer.Typer()
console = Console()

# Global variables
_current_model = os.getenv("OPENCLI_MODEL", "llama-3-8b")
context_provider: Optional[ContextProvider] = None

def version_callback(value: bool) -> None:
    if value:
        from opencli import __version__
        console.print(f"OpenCLI Assistant v{__version__}")
        raise typer.Exit()

@app.callback()
def main_callback(
    version: Optional[bool] = typer.Option(
        None,
        "--version", "-v",
        callback=version_callback,
        is_eager=True,
        help="Show version and exit.",
    )
) -> None:
    """OpenCLI Assistant - Natural language meets your terminal."""
    global context_provider
    load_dotenv()
    
    # Initialize context provider
    context_provider = ContextProvider()
    
    # Set system information
    from opencli.tools.system_info import get_detailed_system_info
    system_info = get_detailed_system_info()
    context_provider.set_system_info(system_info)
    
    print_banner(_current_model)

@app.command()
def run(
    prompt: str = typer.Argument(..., help="Instruction or task to execute."),
    interactive: bool = typer.Option(
        False, "--interactive", "-i", help="Start interactive chat mode."
    ),
    yes: bool = typer.Option(False, "--yes", "-y", help="Execute without confirmation if safe."),
    model: str = typer.Option(_current_model, "--model", "-m", help="LLM model to use."),
) -> None:
    """Execute a one-off prompt or start interactive mode."""
    global _current_model, context_provider
    _current_model = model
    
    if interactive:
        start_interactive_mode(model)
        return

    console.print(f"[bold]Prompt:[/bold] {prompt}")
    
    # Use context provider for translation
    translation = translate_to_command(prompt, context_provider)
    
    if not translation:
        console.print("[yellow]No translation found. Try rephrasing.[/yellow]")
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
        
        # Update context with successful execution
        if context_provider:
            context_provider.update_context_from_response(
                prompt, 
                f"Executed: {translation.command}\nOutput: {out[:100]}..."
            )
    else:
        if err:
            console.print(f"[red]{err}[/red]")
        
        # Update context with failed execution
        if context_provider:
            context_provider.update_context_from_response(
                prompt, 
                f"Failed to execute: {translation.command}\nError: {err[:100]}..."
            )
        raise typer.Exit(code=code)

def start_interactive_mode(model: str) -> None:
    """Start interactive chat mode."""
    global context_provider
    
    console.print("[bold green]Interactive mode starting...[/bold green]")
    console.print("[dim]Type 'exit' or 'quit' to leave interactive mode.[/dim]\n")
    
    while True:
        try:
            user_input = console.input("[bold blue]You:[/bold blue] ").strip()
            if user_input.lower() in ['exit', 'quit']:
                console.print("[dim]Goodbye![/dim]")
                break
                
            if not user_input:
                continue
                
            console.print(f"[bold]Prompt:[/bold] {user_input}")
            
            # Translate to command using context provider
            translation = translate_to_command(user_input, context_provider)
            
            if not translation:
                console.print("[yellow]No translation found. Try rephrasing.[/yellow]")
                continue

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
                continue

            proceed = typer.confirm("Execute this command?", default=False)
            if not proceed:
                console.print("[dim]Cancelled.[/dim]\n")
                
                # Update context with cancelled execution
                if context_provider:
                    context_provider.update_context_from_response(
                        user_input, 
                        "Command cancelled by user"
                    )
                continue

            code, out, err = run_command(translation.command)
            if code == 0:
                if out:
                    console.print(out)
                console.print("[green]Done.[/green]")
                
                # Update context with successful execution
                if context_provider:
                    context_provider.update_context_from_response(
                        user_input, 
                        f"Executed: {translation.command}\nOutput: {out[:100]}..."
                    )
            else:
                if err:
                    console.print(f"[red]{err}[/red]")
                
                # Update context with failed execution
                if context_provider:
                    context_provider.update_context_from_response(
                        user_input, 
                        f"Failed to execute: {translation.command}\nError: {err[:100]}..."
                    )
            
            console.print()  # Add blank line for readability
            
        except KeyboardInterrupt:
            console.print("\n[dim]Goodbye![/dim]")
            break
        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")

def main() -> None:
    app()

if __name__ == "__main__":
    main()