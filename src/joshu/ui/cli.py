"""Main CLI entry point for Joshu."""

from __future__ import annotations

import os
import sys
import logging
from typing import Optional

import typer
from rich.console import Console

from .display import print_banner
from joshu.core.translate import translate_to_command

# Import modular handlers
from .cli_handlers.code_handlers import handle_code_command
from .cli_handlers.commands import (
    handle_config,
    handle_history,
    handle_repeat_last,
    handle_explain_last,
    handle_examples,
    handle_commands_list,
    handle_explain
)
from .cli_handlers.translation_helpers import handle_translation_execution
from .cli_handlers.init import initialize_context, setup_logging

# Import interactive mode
try:
    from .interactive import start_interactive_mode
    PROMPT_TOOLKIT_AVAILABLE = True
except ImportError:
    start_interactive_mode = None
    PROMPT_TOOLKIT_AVAILABLE = False

# Initialize app and console
app = typer.Typer(no_args_is_help=True)
console = Console()

# Global state
_current_model: Optional[str] = None
context_provider = None


def version_callback(value: bool) -> None:
    """Version callback."""
    if value:
        from joshu import __version__
        console.print(f"Joshu v{__version__}")
        raise typer.Exit()


@app.callback()
def main_callback(
    version: Optional[bool] = typer.Option(
        None, "--version", "-v",
        callback=version_callback,
        is_eager=True,
        help="Show version and exit.",
    )
) -> None:
    """Joshu - Natural language meets your terminal."""
    global context_provider, _current_model
    
    config_manager, context_provider, _current_model = initialize_context()
    print_banner(_current_model)


def execute_prompt(prompt: str) -> None:
    """Execute a prompt directly."""
    global _current_model, context_provider
    
    from joshu.core.config import get_config_manager
    config_manager = get_config_manager()
    
    model = config_manager.get("model", "llama-3-8b")
    sandbox = config_manager.get("sandbox_enabled", True)
    auto_execute = config_manager.get("auto_execute", False)
    
    console.print(f"[bold]Prompt:[/bold] {prompt}")
    
    translation = translate_to_command(prompt, context_provider, model)
    
    if not translation:
        console.print("[yellow]No translation found. Try rephrasing.[/yellow]")
        raise typer.Exit(code=2)
    
    console.print(f"[bold]Proposed command:[/bold] [cyan]{translation.command}[/cyan]")
    console.print(f"[dim]{translation.explanation}[/dim]\n")
    
    exit_code = handle_translation_execution(
        translation, prompt, sandbox, auto_execute, context_provider
    )
    raise typer.Exit(code=exit_code)


@app.command()
def config(
    list_config: bool = typer.Option(False, "--list", "-l", help="List all configuration options."),
    get: Optional[str] = typer.Option(None, "--get", "-g", help="Get a specific configuration value."),
    set: Optional[str] = typer.Option(None, "--set", "-s", help="Set a configuration value (format: key=value)."),
    reset: bool = typer.Option(False, "--reset", "-r", help="Reset configuration to defaults."),
    edit: bool = typer.Option(False, "--edit", "-e", help="Open configuration file in editor."),
) -> None:
    """Manage Joshu configuration."""
    handle_config(list_config, get, set, reset, edit)


@app.command()
def interactive(
    model: str = typer.Option(None, "--model", "-m", help="LLM model to use."),
    sandbox: bool = typer.Option(None, "--sandbox", "-s", help="Enable sandbox mode for testing (blocks all destructive commands)."),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable verbose output (show debug logs)."),
) -> None:
    """Start interactive chat mode directly."""
    global _current_model
    
    from joshu.core.config import get_config_manager
    config_manager = get_config_manager()
    
    if model is None:
        model = config_manager.get("model", "llama-3-8b")
    _current_model = model
    
    if sandbox is None:
        sandbox = config_manager.get("sandbox_enabled", True)
    
    setup_logging(verbose)
    
    if start_interactive_mode:
        try:
            start_interactive_mode(model, sandbox, verbose=verbose)
        except ImportError:
            # Fallback to basic mode
            from .cli_handlers.basic_interactive import start_basic_interactive_mode
            from joshu.core.config import get_config_manager
            config_manager = get_config_manager()
            start_basic_interactive_mode(model, sandbox, config_manager, context_provider)
    else:
        # Fallback to basic mode
        from .cli_handlers.basic_interactive import start_basic_interactive_mode
        from joshu.core.config import get_config_manager
        config_manager = get_config_manager()
        start_basic_interactive_mode(model, sandbox, config_manager, context_provider)


@app.command()
def run(
    prompt: Optional[str] = typer.Argument(None, help="Instruction or task to execute."),
    interactive: bool = typer.Option(False, "--interactive", "-i", help="Start interactive chat mode."),
    yes: bool = typer.Option(False, "--yes", "-y", help="Execute without confirmation if safe."),
    model: str = typer.Option(None, "--model", "-m", help="LLM model to use."),
    sandbox: bool = typer.Option(None, "--sandbox", "-s", help="Enable sandbox mode for testing (blocks all destructive commands)."),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable verbose output (show debug logs)."),
) -> None:
    """Execute a one-off prompt or start interactive mode."""
    global _current_model
    
    if interactive:
        from joshu.core.config import get_config_manager
        config_manager = get_config_manager()
        
        if model is None:
            model = config_manager.get("model", "llama-3-8b")
        _current_model = model
        
        if sandbox is None:
            sandbox = config_manager.get("sandbox_enabled", True)
        
        setup_logging(verbose)
        
        if start_interactive_mode:
            try:
                start_interactive_mode(model, sandbox, verbose=verbose)
            except ImportError:
                # Fallback to basic mode
                from .cli_handlers.basic_interactive import start_basic_interactive_mode
                start_basic_interactive_mode(model, sandbox, config_manager, context_provider)
        else:
            # Fallback to basic mode
            from .cli_handlers.basic_interactive import start_basic_interactive_mode
            start_basic_interactive_mode(model, sandbox, config_manager, context_provider)
        return
    
    if not prompt:
        console.print("[red]Error: Prompt is required for non-interactive mode.[/red]")
        console.print("[dim]Use --interactive or -i for interactive mode without a prompt.[/dim]")
        raise typer.Exit(code=1)
    
    execute_prompt(prompt)


@app.command()
def history(
    limit: int = typer.Option(10, "--limit", "-n", help="Number of history entries to show."),
) -> None:
    """Show command execution history."""
    global context_provider
    handle_history(limit, context_provider)


@app.command()
def repeat_last() -> None:
    """Repeat the last executed command."""
    global context_provider
    handle_repeat_last(context_provider)


@app.command()
def explain_last() -> None:
    """Explain the last executed command."""
    global context_provider
    handle_explain_last(context_provider)


@app.command()
def examples() -> None:
    """Show usage examples for Joshu."""
    handle_examples()


@app.command()
def commands(
    category: str = typer.Argument(None, help="Category of commands to show (e.g., file, system, network)")
) -> None:
    """Show available command categories and examples."""
    handle_commands_list(category)


@app.command()
def explain(
    command: str = typer.Argument(..., help="Command or topic to explain")
) -> None:
    """Explain a specific command or topic."""
    global context_provider
    handle_explain(command, context_provider)


@app.command()
def code(
    prompt: str = typer.Argument(..., help="Code generation or editing prompt"),
    file: Optional[str] = typer.Option(None, "--file", "-f", help="File to edit or create"),
    language: Optional[str] = typer.Option(None, "--language", "-l", help="Programming language"),
    dry_run: bool = typer.Option(False, "--dry-run", "-d", help="Show what would be done without making changes"),
) -> None:
    """Generate, edit, explain, debug, or refactor code based on natural language prompts."""
    console.print(f"[bold]Code Assistant:[/bold] {prompt}")
    handle_code_command(prompt, file, language, dry_run)


@app.command()
def cache_stats() -> None:
    """Show translation cache statistics."""
    from joshu.core.translation_cache import TranslationCache
    from joshu.core.config import get_config_manager
    
    try:
        config_manager = get_config_manager()
        
        if not config_manager.get("cache_enabled", True):
            console.print("[yellow]Translation cache is disabled in configuration.[/yellow]")
            console.print("Enable it with: [cyan]joshu config --set cache_enabled=true[/cyan]")
            return
        
        cache_dir = config_manager.get("cache_dir", "~/.joshu/cache")
        similarity_threshold = config_manager.get("cache_similarity_threshold", 0.85)
        max_entries = config_manager.get("cache_max_entries", 1000)
        
        cache = TranslationCache(
            cache_dir=cache_dir,
            similarity_threshold=similarity_threshold,
            max_entries=max_entries
        )
        
        stats = cache.get_stats()
        
        console.print("\n[bold cyan]Translation Cache Statistics:[/bold cyan]")
        console.print(f"  Total entries: [green]{stats['total_entries']}[/green] / {max_entries}")
        console.print(f"  Total cache hits: [green]{stats['total_hits']}[/green]")
        console.print(f"  Cache file size: [green]{stats['cache_file_size']:,}[/green] bytes")
        console.print(f"  Similarity threshold: [green]{similarity_threshold}[/green]")
        console.print(f"  Cache location: [cyan]{cache.cache_file}[/cyan]")
        
        if stats['total_entries'] > 0:
            hit_rate = (stats['total_hits'] / stats['total_entries']) * 100 if stats['total_entries'] > 0 else 0
            console.print(f"  Average hits per entry: [green]{hit_rate:.1f}%[/green]")
        console.print()
        
    except Exception as e:
        console.print(f"[red]Error getting cache statistics: {e}[/red]")


@app.command()
def cache_clear() -> None:
    """Clear the translation cache."""
    from joshu.core.translation_cache import TranslationCache
    from joshu.core.config import get_config_manager
    
    try:
        config_manager = get_config_manager()
        cache_dir = config_manager.get("cache_dir", "~/.joshu/cache")
        similarity_threshold = config_manager.get("cache_similarity_threshold", 0.85)
        max_entries = config_manager.get("cache_max_entries", 1000)
        
        cache = TranslationCache(
            cache_dir=cache_dir,
            similarity_threshold=similarity_threshold,
            max_entries=max_entries
        )
        
        cache.clear()
        console.print("[green]✓[/green] Translation cache cleared successfully.")
        
    except Exception as e:
        console.print(f"[red]Error clearing cache: {e}[/red]")



def main() -> None:
    """Main entry point."""
    if len(sys.argv) > 1:
        first_arg = sys.argv[1]
        known_commands = ["config", "run", "history", "repeat-last", "explain-last", "examples", "commands", "explain", "code", "cache-stats", "cache-clear", "--help", "-h", "--version", "-v"]
        
        if first_arg not in known_commands and not first_arg.startswith("-"):
            prompt = " ".join(sys.argv[1:])
            
            global context_provider, _current_model
            config_manager, context_provider, _current_model = initialize_context()
            print_banner(_current_model)
            
            try:
                execute_prompt(prompt)
            except Exception as e:
                console.print(f"[red]Error: {e}[/red]")
                sys.exit(1)
            
            sys.exit(0)
    
    app()


if __name__ == "__main__":
    main()
