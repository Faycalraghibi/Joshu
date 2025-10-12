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
    global context_provider, _current_model
    load_dotenv()
    
    # Initialize configuration manager
    from opencli.core.config import get_config_manager
    config_manager = get_config_manager()
    
    # Set current model from configuration
    _current_model = config_manager.get("model", "llama-3-8b")
    
    # Initialize context provider
    context_provider = ContextProvider()
    
    # Set system information
    from opencli.tools.system_info import get_detailed_system_info
    system_info = get_detailed_system_info()
    context_provider.set_system_info(system_info)
    
    print_banner(_current_model)


@app.command()
def config(
    list_config: bool = typer.Option(False, "--list", "-l", help="List all configuration options."),
    get: Optional[str] = typer.Option(None, "--get", "-g", help="Get a specific configuration value."),
    set: Optional[str] = typer.Option(None, "--set", "-s", help="Set a configuration value (format: key=value)."),
    reset: bool = typer.Option(False, "--reset", "-r", help="Reset configuration to defaults."),
    edit: bool = typer.Option(False, "--edit", "-e", help="Open configuration file in editor."),
) -> None:
    """Manage OpenCLI configuration."""
    from opencli.core.config import get_config_manager
    
    config_manager = get_config_manager()
    
    if list_config:
        # List all configuration options
        console.print("[bold]Current Configuration:[/bold]")
        config_dict = config_manager.config.to_dict()
        for key, value in config_dict.items():
            console.print(f"  {key}: {value}")
        return
    
    if get:
        # Get specific configuration value
        value = config_manager.get(get)
        if value is not None:
            console.print(f"{get}: {value}")
        else:
            console.print(f"[yellow]Configuration key '{get}' not found.[/yellow]")
        return
    
    if set:
        # Set configuration value
        if "=" not in set:
            console.print("[red]Invalid format. Use key=value[/red]")
            raise typer.Exit(code=1)
        
        key, value = set.split("=", 1)
        
        # Try to convert value to appropriate type
        if value.lower() in ("true", "false"):
            value = value.lower() == "true"
        elif value.isdigit():
            value = int(value)
        elif value.replace(".", "").isdigit():
            value = float(value)
        
        if config_manager.set(key, value):
            config_manager.save_config()
            console.print(f"[green]Set {key} = {value}[/green]")
        else:
            console.print(f"[red]Invalid configuration key: {key}[/red]")
            raise typer.Exit(code=1)
        return
    
    if reset:
        # Reset configuration to defaults
        config_manager.reset_to_defaults()
        config_manager.save_config()
        console.print("[green]Configuration reset to defaults.[/green]")
        return
    
    if edit:
        # Open configuration file in editor
        config_path = config_manager.get_config_path()
        # Use appropriate default editor based on OS
        if os.name == 'nt':  # Windows
            editor = os.environ.get("EDITOR", "notepad")
        else:  # Unix-like systems
            editor = os.environ.get("EDITOR", "nano")
        
        try:
            import subprocess
            subprocess.run([editor, str(config_path)])
            # Reload config after editing
            config_manager.load_config()
            console.print("[green]Configuration file edited and reloaded.[/green]")
        except Exception as e:
            console.print(f"[red]Failed to open editor: {e}[/red]")
            console.print(f"[yellow]You can manually edit: {config_path}[/yellow]")
        return

    # If no options provided, show help
    console.print("[bold]OpenCLI Configuration Manager[/bold]")
    console.print("Use --help for more information.")


@app.command()
def run(
    prompt: str = typer.Argument(None, help="Instruction or task to execute."),
    interactive: bool = typer.Option(
        False, "--interactive", "-i", help="Start interactive chat mode."
    ),
    yes: bool = typer.Option(False, "--yes", "-y", help="Execute without confirmation if safe."),
    model: str = typer.Option(None, "--model", "-m", help="LLM model to use."),
    sandbox: bool = typer.Option(None, "--sandbox", "-s", help="Enable sandbox mode for testing (blocks all destructive commands)."),
) -> None:
    """Execute a one-off prompt or start interactive mode."""
    global _current_model, context_provider
    
    # Get configuration manager
    from opencli.core.config import get_config_manager
    config_manager = get_config_manager()
    
    # Use provided model or fall back to configured model
    if model is None:
        model = config_manager.get("model", "llama-3-8b")
    _current_model = model
    
    # Use provided sandbox setting or fall back to configured setting
    if sandbox is None:
        sandbox = config_manager.get("sandbox_enabled", True)
    
    # Use configured auto_execute setting if --yes not provided
    if not yes:
        yes = config_manager.get("auto_execute", False)
    
    # Handle interactive mode
    if interactive:
        start_interactive_mode(model, sandbox)
        return
    
    # For non-interactive mode, prompt is required
    if not prompt:
        console.print("[red]Error: Prompt is required for non-interactive mode.[/red]")
        console.print("[dim]Use --interactive or -i for interactive mode without a prompt.[/dim]")
        raise typer.Exit(code=1)

    console.print(f"[bold]Prompt:[/bold] {prompt}")
    
    # Use context provider for translation with specified model
    translation = translate_to_command(prompt, context_provider, model)
    
    if not translation:
        console.print("[yellow]No translation found. Try rephrasing.[/yellow]")
        raise typer.Exit(code=2)

    console.print(f"[bold]Proposed command:[/bold] [cyan]{translation.command}[/cyan]")
    console.print(f"[dim]{translation.explanation}[/dim]\n")
    report = assess_command_safety(translation.command, sandbox)
    
    # Enhanced safety feedback
    if not report.safe:
        if report.danger_level == "CRITICAL":
            console.print("[bold red]⚠️  DANGER: This command could cause serious damage[/bold red]")
        elif report.danger_level == "HIGH":
            console.print("[bold yellow]⚠️  WARNING: This command is potentially dangerous[/bold yellow]")
        elif report.danger_level == "MEDIUM":
            console.print("[yellow]⚠️  CAUTION: This command requires careful consideration[/yellow]")
        else:
            console.print("[yellow]⚠️  Command flagged for review[/yellow]")
            
        for r in report.reasons:
            console.print(f" - {r}")
        if report.suggested_alternative:
            console.print(
                f"[yellow]Suggested safer alternative:[/yellow] {report.suggested_alternative}"
            )
        raise typer.Exit(code=3)

    # If auto_execute is enabled or user confirms, execute the command
    if yes:
        console.print("[dim]Auto-executing command (auto_execute enabled in config)[/dim]")
    else:
        proceed = typer.confirm("Execute this command?", default=False)
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

def start_interactive_mode(model: str, sandbox: bool = False) -> None:
    """Start interactive chat mode."""
    global context_provider
    
    # Get configuration manager
    from opencli.core.config import get_config_manager
    config_manager = get_config_manager()
    
    # Use configured auto_execute setting
    auto_execute = config_manager.get("auto_execute", False)
    
    mode_text = " (sandbox mode)" if sandbox else ""
    console.print(f"[bold green]Interactive mode starting...{mode_text}[/bold green]")
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
            
            # Translate to command using context provider with specified model
            translation = translate_to_command(user_input, context_provider, model)
            
            if not translation:
                console.print("[yellow]No translation found. Try rephrasing.[/yellow]")
                continue

            console.print(f"[bold]Proposed command:[/bold] [cyan]{translation.command}[/cyan]")
            console.print(f"[dim]{translation.explanation}[/dim]\n")
            
            report = assess_command_safety(translation.command, sandbox)
            
            # Enhanced safety feedback
            if not report.safe:
                if report.danger_level == "CRITICAL":
                    console.print("[bold red]⚠️  DANGER: This command could cause serious damage[/bold red]")
                elif report.danger_level == "HIGH":
                    console.print("[bold yellow]⚠️  WARNING: This command is potentially dangerous[/bold yellow]")
                elif report.danger_level == "MEDIUM":
                    console.print("[yellow]⚠️  CAUTION: This command requires careful consideration[/yellow]")
                else:
                    console.print("[yellow]⚠️  Command flagged for review[/yellow]")
                    
                for r in report.reasons:
                    console.print(f" - {r}")
                if report.suggested_alternative:
                    console.print(
                        f"[yellow]Suggested safer alternative:[/yellow] {report.suggested_alternative}"
                    )
                continue

            # If auto_execute is enabled, execute without confirmation
            if auto_execute:
                console.print("[dim]Auto-executing command (auto_execute enabled in config)[/dim]")
                proceed = True
            else:
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