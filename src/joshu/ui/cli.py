from __future__ import annotations

import os
import sys
import logging
from pathlib import Path
from typing import Optional, List

import typer
from rich.console import Console
from dotenv import load_dotenv

# Add prompt_toolkit imports with proper error handling
try:
    from prompt_toolkit import PromptSession
    from prompt_toolkit.history import FileHistory, InMemoryHistory
    from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
    from prompt_toolkit.key_binding import KeyBindings
    from prompt_toolkit.keys import Keys
    from prompt_toolkit.styles import Style
    from prompt_toolkit.formatted_text import HTML
    from prompt_toolkit.application import run_in_terminal
    from prompt_toolkit.buffer import Buffer
    from prompt_toolkit.enums import EditingMode
except ImportError:
    PromptSession = None
    FileHistory = None
    InMemoryHistory = None
    AutoSuggestFromHistory = None
    KeyBindings = None
    Keys = None
    Style = None
    HTML = None
    run_in_terminal = None
    Buffer = None
    EditingMode = None

from .display import print_banner
from joshu.core.translate import translate_to_command
from joshu.core.safety import assess_command_safety
from joshu.tools.shell import run_command
from joshu.core.context import ConversationContext
from joshu.core.context_provider import ContextProvider
from joshu.tools.code_editor import CodeEditor, CodeEdit

# Import the interactive mode function
try:
    from joshu.ui.interactive import start_interactive_mode as start_enhanced_interactive_mode
    PROMPT_TOOLKIT_AVAILABLE = True
except ImportError:
    start_enhanced_interactive_mode = None
    PROMPT_TOOLKIT_AVAILABLE = False

# Set up logging with a higher level to reduce verbose output
# Only show warnings and errors by default, unless verbose mode is enabled
logging.basicConfig(level=logging.WARNING, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

# Reduce logging from specific modules that are too verbose
logging.getLogger('httpx').setLevel(logging.WARNING)
logging.getLogger('joshu.core.translate').setLevel(logging.INFO)  # Still show translation info

app = typer.Typer(no_args_is_help=True)  # Show help when no args provided
console = Console()

# Global variables
_current_model = os.getenv("JOSHU_MODEL", "llama-3-8b")
context_provider: Optional[ContextProvider] = None

def version_callback(value: bool) -> None:
    if value:
        from joshu import __version__
        console.print(f"Joshu v{__version__}")
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
    """Joshu - Natural language meets your terminal."""
    global context_provider, _current_model
    load_dotenv()
    
    # Initialize configuration manager
    from joshu.core.config import get_config_manager
    config_manager = get_config_manager()
    
    # Set current model from configuration
    _current_model = config_manager.get("model", "llama-3-8b")
    
    # Initialize context provider
    context_provider = ContextProvider()
    
    # Set system information
    from joshu.tools.system_info import get_detailed_system_info
    system_info = get_detailed_system_info()
    context_provider.set_system_info(system_info)
    
    # Ensure cloud usage is enabled if a cloud model is configured
    import os
    configured_model = os.getenv("OPENROUTER_MODEL") or "llama-3-8b"
    cloud_models = ["deepseek", "tongyi", "qwen", "kimi", "agentica", "glm"]
    
    if any(model in configured_model.lower() for model in cloud_models):
        # Set JOSHU_USE_CLOUD to true if not already set
        if not os.getenv("JOSHU_USE_CLOUD"):
            os.environ["JOSHU_USE_CLOUD"] = "true"
    
    # Establish connection when assistant is launched
    try:
        from joshu.core.translate import establish_connection
        if establish_connection(_current_model):
            logger.debug("Connection established successfully")
        else:
            logger.debug("Failed to establish connection, will retry on first request")
    except Exception as e:
        logger.debug(f"Connection establishment skipped: {e}")
    
    print_banner(_current_model)


def execute_prompt(prompt: str) -> None:
    """Execute a prompt directly."""
    global _current_model, context_provider
    
    # Get configuration manager
    from joshu.core.config import get_config_manager
    config_manager = get_config_manager()
    
    # Get current model and settings
    model = config_manager.get("model", "llama-3-8b")
    sandbox = config_manager.get("sandbox_enabled", True)
    auto_execute = config_manager.get("auto_execute", False)
    
    console.print(f"[bold]Prompt:[/bold] {prompt}")
    
    # Use context provider for translation with specified model
    translation = translate_to_command(prompt, context_provider, model)
    
    if not translation:
        console.print("[yellow]No translation found. Try rephrasing.[/yellow]")
        raise typer.Exit(code=2)

    console.print(f"[bold]Proposed command:[/bold] [cyan]{translation.command}[/cyan]")
    console.print(f"[dim]{translation.explanation}[/dim]\n")
    
    # Check if this needs execution (conversational responses don't need confirmation)
    # Check the flag first
    needs_execution = getattr(translation, 'needs_execution', True)
    
    # SAFETY CHECK: Also check explanation and command format directly as backup
    # This ensures conversational responses are never prompted for execution
    explanation_lower = translation.explanation.lower()
    command_normalized = translation.command.replace('\\"', '"').replace("\\'", "'")
    
    # Conversational indicators in explanation
    conversational_keywords = [
        "conversational response", "direct response", "direct answer",
        "to user's query", "to user's question", "user's query", "user's question",
        "answering", "providing answer", "providing response"
    ]
    
    # Check if explanation indicates conversational
    is_conversational_explanation = any(keyword in explanation_lower for keyword in conversational_keywords)
    
    # Check if command is a long informational echo (conversational)
    is_conversational_command = (
        '"""' in command_normalized or  # Has triple quotes
        (command_normalized.startswith('echo "') and len(translation.command) > 100)
    )
    
    # Override needs_execution if we detect conversational response
    if is_conversational_explanation or is_conversational_command:
        needs_execution = False
    
    if not needs_execution:
        # This is a conversational response - execute it directly without asking
        code, out, err = run_command(translation.command)
        if code == 0:
            if out:
                console.print(out)
        else:
            if err:
                console.print(f"[red]{err}[/red]")
        raise typer.Exit(code=0)
    
    # Check if this is a code generation request that should use the code command
    if "code command" in translation.explanation.lower() or "code' command" in translation.explanation.lower():
        console.print("[yellow]💡 Tip: For code generation requests, use the 'code' command:[/yellow]")
        console.print(f"[yellow]   joshu code \"{prompt}\"[/yellow]")
        console.print("[yellow]This will generate the code directly instead of trying to translate to a shell command.[/yellow]")
        raise typer.Exit(code=0)

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
    if auto_execute:
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


@app.command()
def config(
    list_config: bool = typer.Option(False, "--list", "-l", help="List all configuration options."),
    get: Optional[str] = typer.Option(None, "--get", "-g", help="Get a specific configuration value."),
    set: Optional[str] = typer.Option(None, "--set", "-s", help="Set a configuration value (format: key=value)."),
    reset: bool = typer.Option(False, "--reset", "-r", help="Reset configuration to defaults."),
    edit: bool = typer.Option(False, "--edit", "-e", help="Open configuration file in editor."),
) -> None:
    """Manage Joshu configuration."""
    from joshu.core.config import get_config_manager
    
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
    console.print("[bold]Joshu Configuration Manager[/bold]")
    console.print("Use --help for more information.")


@app.command()
def interactive(
    model: str = typer.Option(None, "--model", "-m", help="LLM model to use."),
    sandbox: bool = typer.Option(None, "--sandbox", "-s", help="Enable sandbox mode for testing (blocks all destructive commands)."),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable verbose output (show debug logs)."),
) -> None:
    """Start interactive chat mode directly."""
    global _current_model, context_provider
    
    # Get configuration manager
    from joshu.core.config import get_config_manager
    config_manager = get_config_manager()
    
    # Use provided model or fall back to configured model
    if model is None:
        model = config_manager.get("model", "llama-3-8b")
    _current_model = model
    
    # Use provided sandbox setting or fall back to configured setting
    if sandbox is None:
        sandbox = config_manager.get("sandbox_enabled", True)
    
    start_interactive_mode(model, sandbox, verbose=verbose)


@app.command()
def run(
    prompt: Optional[str] = typer.Argument(None, help="Instruction or task to execute."),
    interactive: bool = typer.Option(
        False, "--interactive", "-i", help="Start interactive chat mode."
    ),
    yes: bool = typer.Option(False, "--yes", "-y", help="Execute without confirmation if safe."),
    model: str = typer.Option(None, "--model", "-m", help="LLM model to use."),
    sandbox: bool = typer.Option(None, "--sandbox", "-s", help="Enable sandbox mode for testing (blocks all destructive commands)."),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable verbose output (show debug logs)."),
) -> None:
    """Execute a one-off prompt or start interactive mode."""
    global _current_model, context_provider
    
    # Handle interactive mode
    if interactive:
        # Get configuration manager
        from joshu.core.config import get_config_manager
        config_manager = get_config_manager()
        
        # Use provided model or fall back to configured model
        if model is None:
            model = config_manager.get("model", "llama-3-8b")
        _current_model = model
        
        # Use provided sandbox setting or fall back to configured setting
        if sandbox is None:
            sandbox = config_manager.get("sandbox_enabled", True)
        
        start_interactive_mode(model, sandbox, verbose=verbose)
        return
    
    # For non-interactive mode, prompt is required
    if not prompt:
        console.print("[red]Error: Prompt is required for non-interactive mode.[/red]")
        console.print("[dim]Use --interactive or -i for interactive mode without a prompt.[/dim]")
        raise typer.Exit(code=1)
    
    # Execute the prompt
    execute_prompt(prompt)


@app.command()
def history(
    limit: int = typer.Option(10, "--limit", "-n", help="Number of history entries to show."),
) -> None:
    """Show command execution history."""
    global context_provider
    
    # Initialize context provider if not already initialized
    if context_provider is None:
        context_provider = ContextProvider()
    
    # Get conversation history
    history_messages = context_provider.conversation_context.messages
    
    if not history_messages:
        console.print("[yellow]No history available.[/yellow]")
        return
    
    # Filter to only show user commands (not assistant responses)
    user_commands = [msg for msg in history_messages if msg["role"] == "user"]
    
    if not user_commands:
        console.print("[yellow]No command history available.[/yellow]")
        return
    
    # Limit to the requested number of entries
    user_commands = user_commands[-limit:]
    
    console.print(f"[bold]Command History (last {len(user_commands)} entries):[/bold]")
    for i, msg in enumerate(user_commands, 1):
        console.print(f"  {i}. {msg['content']}")


@app.command()
def repeat_last() -> None:
    """Repeat the last executed command."""
    global context_provider, _current_model
    
    # Initialize context provider if not already initialized
    if context_provider is None:
        context_provider = ContextProvider()
    
    # Get configuration manager
    from joshu.core.config import get_config_manager
    config_manager = get_config_manager()
    
    # Get current model and sandbox settings
    model = config_manager.get("model", "llama-3-8b")
    sandbox = config_manager.get("sandbox_enabled", True)
    auto_execute = config_manager.get("auto_execute", False)
    
    # Get conversation history
    history_messages = context_provider.conversation_context.messages
    
    if not history_messages:
        console.print("[yellow]No history available to repeat.[/yellow]")
        raise typer.Exit(code=1)
    
    # Find the last user command
    last_command = None
    for msg in reversed(history_messages):
        if msg["role"] == "user":
            last_command = msg["content"]
            break
    
    if not last_command:
        console.print("[yellow]No previous command found to repeat.[/yellow]")
        raise typer.Exit(code=1)
    
    console.print(f"[bold]Repeating last command:[/bold] {last_command}")
    
    # Use context provider for translation with specified model
    from joshu.core.translate import translate_to_command
    translation = translate_to_command(last_command, context_provider, model)
    
    if not translation:
        console.print("[yellow]No translation found for the last command.[/yellow]")
        raise typer.Exit(code=2)

    console.print(f"[bold]Proposed command:[/bold] [cyan]{translation.command}[/cyan]")
    console.print(f"[dim]{translation.explanation}[/dim]\n")
    
    from joshu.core.safety import assess_command_safety
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
    if auto_execute:
        console.print("[dim]Auto-executing command (auto_execute enabled in config)[/dim]")
    else:
        proceed = typer.confirm("Execute this command?", default=False)
        if not proceed:
            console.print("[dim]Cancelled.[/dim]\n")
            raise typer.Exit()

    from joshu.tools.shell import run_command
    code, out, err = run_command(translation.command)
    if code == 0:
        if out:
            console.print(out)
        console.print("[green]Done.[/green]")
        
        # Update context with successful execution
        if context_provider:
            context_provider.update_context_from_response(
                last_command, 
                f"Executed: {translation.command}\nOutput: {out[:100]}..."
            )
    else:
        if err:
            console.print(f"[red]{err}[/red]")
        
        # Update context with failed execution
        if context_provider:
            context_provider.update_context_from_response(
                last_command, 
                f"Failed to execute: {translation.command}\nError: {err[:100]}..."
            )
        raise typer.Exit(code=code)


@app.command()
def explain_last() -> None:
    """Explain the last executed command."""
    global context_provider, _current_model
    
    # Initialize context provider if not already initialized
    if context_provider is None:
        context_provider = ContextProvider()
    
    # Get configuration manager
    from joshu.core.config import get_config_manager
    config_manager = get_config_manager()
    
    # Get current model
    model = config_manager.get("model", "llama-3-8b")
    
    # Get conversation history
    history_messages = context_provider.conversation_context.messages
    
    if not history_messages:
        console.print("[yellow]No history available to explain.[/yellow]")
        raise typer.Exit(code=1)
    
    # Find the last user-assistant interaction
    last_user_command = None
    last_assistant_response = None
    
    # Iterate through messages in reverse to find the last interaction
    for i in range(len(history_messages) - 1, -1, -1):
        msg = history_messages[i]
        if msg["role"] == "assistant" and not last_assistant_response:
            last_assistant_response = msg["content"]
        elif msg["role"] == "user" and not last_user_command:
            last_user_command = msg["content"]
        
        # If we found both, we can break
        if last_user_command and last_assistant_response:
            break
    
    if not last_user_command or not last_assistant_response:
        console.print("[yellow]No complete command history found to explain.[/yellow]")
        raise typer.Exit(code=1)
    
    console.print(f"[bold]Last Command:[/bold] {last_user_command}")
    console.print(f"[bold]Explanation:[/bold] {last_assistant_response}")


@app.command()
def examples() -> None:
    """Show usage examples for Joshu."""
    console.print("[bold]Joshu Usage Examples[/bold]\n")
    
    console.print("[cyan]Basic Commands:[/cyan]")
    console.print("  joshu \"list all python files modified in the last week\"")
    console.print("  joshu \"create a backup of my project directory\"")
    console.print("  joshu \"show me memory usage of running processes\"\n")
    
    console.print("[cyan]File System Intelligence:[/cyan]")
    console.print("  joshu \"show me the structure of this project\"")
    console.print("  joshu \"find configuration files\"")
    console.print("  joshu \"what's in the log directory?\"")
    console.print("  joshu \"backup my source code\"\n")
    
    console.print("[cyan]Code Generation:[/cyan]")
    console.print("  joshu \"write a python function to parse CSV files\"")
    console.print("  joshu \"debug this bash script: ./deploy.sh\"")
    console.print("  joshu \"explain what this regex does: ^[a-zA-Z0-9+_.-]+@[a-zA-Z0-9.-]+$\"\n")
    
    console.print("[cyan]Interactive Mode:[/cyan]")
    console.print("  joshu --interactive\n")
    
    console.print("[cyan]Safety Features:[/cyan]")
    console.print("  joshu \"delete all files in /home\"  # Will be blocked for safety")
    console.print("  joshu --sandbox \"delete all files\"  # Sandbox mode for testing\n")
    
    console.print("[cyan]Configuration:[/cyan]")
    console.print("  joshu config --list")
    console.print("  joshu config --set auto_execute=true")
    console.print("  joshu config --edit\n")


@app.command()
def commands(
    category: str = typer.Argument(None, help="Category of commands to show (e.g., file, system, network)")
) -> None:
    """Show available command categories and examples."""
    console.print("[bold]Joshu Command Categories[/bold]\n")
    
    if category is None:
        # Show all categories
        console.print("[cyan]Available Categories:[/cyan]")
        console.print("  file      - File system operations")
        console.print("  system    - System information and management")
        console.print("  network   - Network operations")
        console.print("  process   - Process management")
        console.print("  security  - Security-related commands")
        console.print("  git       - Git version control")
        console.print("  docker    - Docker container management")
        console.print("\nUse 'joshu --commands [category]' to see examples for a specific category.\n")
        return
    
    category = category.lower()
    
    if category == "file":
        console.print("[bold]File System Commands:[/bold]")
        console.print("  List files:                    joshu \"list all files in current directory\"")
        console.print("  Find files:                    joshu \"find all python files\"")
        console.print("  Show directory structure:      joshu \"show me the structure of this project\"")
        console.print("  Check disk usage:              joshu \"show disk usage of current directory\"")
        console.print("  Find large files:              joshu \"find large files over 100MB\"")
        console.print("  Backup files:                  joshu \"backup my source code\"")
    elif category == "system":
        console.print("[bold]System Commands:[/bold]")
        console.print("  System information:            joshu \"show system information\"")
        console.print("  Memory usage:                  joshu \"show memory usage\"")
        console.print("  CPU information:               joshu \"show CPU information\"")
        console.print("  Network interfaces:            joshu \"list network interfaces\"")
        console.print("  Running processes:             joshu \"show running processes\"")
    elif category == "network":
        console.print("[bold]Network Commands:[/bold]")
        console.print("  Check connectivity:            joshu \"check if google.com is reachable\"")
        console.print("  Port scanning:                 joshu \"scan open ports on localhost\"")
        console.print("  Download file:                 joshu \"download https://example.com/file.txt\"")
        console.print("  Check IP address:              joshu \"what is my IP address\"")
    elif category == "process":
        console.print("[bold]Process Management Commands:[/bold]")
        console.print("  List processes:                joshu \"show running processes\"")
        console.print("  Kill process:                  joshu \"kill process named python\"")
        console.print("  Monitor process:               joshu \"monitor process with PID 1234\"")
    elif category == "security":
        console.print("[bold]Security Commands:[/bold]")
        console.print("  Check file permissions:        joshu \"check permissions of config.yaml\"")
        console.print("  Generate password:             joshu \"generate a secure password\"")
        console.print("  Check open ports:              joshu \"list open network ports\"")
    elif category == "git":
        console.print("[bold]Git Commands:[/bold]")
        console.print("  Git status:                    joshu \"show git status\"")
        console.print("  Git commit:                    joshu \"commit changes with message 'Update README'\"")
        console.print("  Git push:                      joshu \"push changes to remote repository\"")
        console.print("  Git branch:                    joshu \"create new branch feature/new-feature\"")
    elif category == "docker":
        console.print("[bold]Docker Commands:[/bold]")
        console.print("  List containers:               joshu \"list running docker containers\"")
        console.print("  Start container:               joshu \"start container named my-app\"")
        console.print("  Stop container:                joshu \"stop container with ID abc123\"")
        console.print("  Build image:                   joshu \"build docker image from Dockerfile\"")
    else:
        console.print(f"[yellow]Unknown category: {category}[/yellow]")
        console.print("[cyan]Available Categories:[/cyan]")
        console.print("  file, system, network, process, security, git, docker")


@app.command()
def explain(
    command: str = typer.Argument(..., help="Command or topic to explain")
) -> None:
    """Explain a specific command or topic."""
    # Get configuration manager
    from joshu.core.config import get_config_manager
    config_manager = get_config_manager()
    
    # Get current model
    model = config_manager.get("model", "llama-3-8b")
    
    # Use context provider if available
    global context_provider
    
    # Create a prompt to explain the command
    prompt = f"Explain the '{command}' command in a clear and concise way. Include common usage examples and important options."
    
    # Use the translation system to get an explanation
    from joshu.core.translate import translate_to_command
    translation = translate_to_command(prompt, context_provider, model)
    
    if translation and translation.command.startswith("echo"):
        # Extract the explanation from the echo command
        import re
        match = re.search(r'echo\s+["\']{3}(.*?)["\']{3}', translation.command, re.DOTALL)
        if match:
            explanation = match.group(1)
            console.print(f"[bold]Explanation of '{command}':[/bold]\n{explanation}")
            return
    
    # Fallback to a direct explanation
    explanations = {
        "tar": "The tar command is used to create and manipulate tar archives. Common usage:\n"
               "  tar -czf archive.tar.gz directory/    # Create compressed archive\n"
               "  tar -xzf archive.tar.gz               # Extract compressed archive\n"
               "  tar -tf archive.tar.gz                # List contents of archive",
        "git": "Git is a distributed version control system. Common commands:\n"
               "  git status          # Show working directory status\n"
               "  git add .           # Stage all changes\n"
               "  git commit -m \"message\"  # Commit staged changes\n"
               "  git push            # Push commits to remote repository\n"
               "  git pull            # Pull changes from remote repository",
        "docker": "Docker is a containerization platform. Common commands:\n"
                  "  docker run image    # Run a container from an image\n"
                  "  docker ps           # List running containers\n"
                  "  docker build .      # Build an image from Dockerfile\n"
                  "  docker stop id      # Stop a running container",
        "ls": "The ls command lists directory contents. Common usage:\n"
             "  ls -la              # List all files with details\n"
             "  ls *.py             # List only Python files\n"
             "  ls -R               # List files recursively",
        "grep": "The grep command searches for patterns in files. Common usage:\n"
                "  grep pattern file   # Search for pattern in file\n"
                "  grep -r pattern .   # Search recursively in current directory\n"
                "  grep -i pattern file # Case-insensitive search",
    }
    
    if command.lower() in explanations:
        console.print(f"[bold]Explanation of '{command}':[/bold]\n{explanations[command.lower()]}")
    else:
        console.print(f"[yellow]No specific explanation available for '{command}'.[/yellow]")
        console.print("Try asking about common commands like: tar, git, docker, ls, grep")


@app.command()
def code(
    prompt: str = typer.Argument(..., help="Code generation or editing prompt"),
    file: Optional[str] = typer.Option(None, "--file", "-f", help="File to edit or create"),
    language: Optional[str] = typer.Option(None, "--language", "-l", help="Programming language"),
    dry_run: bool = typer.Option(False, "--dry-run", "-d", help="Show what would be done without making changes"),
) -> None:
    """Generate, edit, explain, debug, or refactor code based on natural language prompts."""
    console.print(f"[bold]Code Assistant:[/bold] {prompt}")
    
    # Import code editor
    from joshu.tools.code_editor import CodeEditor
    editor = CodeEditor()
    
    # Get configuration
    from joshu.core.config import get_config_manager
    config_manager = get_config_manager()
    model = config_manager.get("model", "llama-3-8b")
    
    # Use context provider if available
    global context_provider
    
    # Determine what kind of operation this is based on the prompt
    prompt_lower = prompt.lower()
    
    if file:
        # File-specific operations
        if "edit" in prompt_lower or "modify" in prompt_lower or "update" in prompt_lower:
            # File editing operation
            _handle_file_edit(editor, prompt, file, language, dry_run)
        elif "create" in prompt_lower or "generate" in prompt_lower or "write" in prompt_lower:
            # File creation operation
            _handle_file_create(editor, prompt, file, language, dry_run)
        else:
            # Default to editing if file is specified
            _handle_file_edit(editor, prompt, file, language, dry_run)
    else:
        # General code operations
        if "explain" in prompt_lower or "what does this code do" in prompt_lower:
            # Code explanation
            _handle_code_explanation(editor, prompt, dry_run)
        elif ("debug" in prompt_lower or "fix" in prompt_lower) and "error" in prompt_lower:
            # Code debugging - only trigger if both debug/fix and error are present
            _handle_code_debugging(editor, prompt, dry_run)
        elif "refactor" in prompt_lower or "optimize" in prompt_lower or "improve" in prompt_lower:
            # Code refactoring
            _handle_code_refactoring(editor, prompt, dry_run)
        else:
            # Default to code generation
            _handle_code_generation(editor, prompt, language, dry_run)


def _handle_file_edit(editor: CodeEditor, prompt: str, file_path: str, language: Optional[str], dry_run: bool) -> None:
    """Handle file editing operations."""
    console.print(f"[bold]Editing file:[/bold] {file_path}")
    
    try:
        # Check if file exists
        if not os.path.exists(file_path):
            console.print(f"[red]File {file_path} does not exist.[/red]")
            console.print("[yellow]Use file creation instead: joshu code 'create ...' --file {file_path}[/yellow]")
            return
        
        # Ask for confirmation before editing
        if not dry_run:
            console.print(f"[yellow]⚠️  This will modify {file_path}[/yellow]")
            if not typer.confirm("Proceed with editing?", default=False):
                console.print("[dim]Edit cancelled.[/dim]")
                return
        
        # Use the edit_file method which uses LLM
        result = editor.edit_file(file_path, prompt)
        
        if dry_run:
            # For dry run, we would show what would be changed
            # Since edit_file requires actual execution, we'll show a preview message
            console.print(f"[bold]Proposed edit:[/bold] {prompt}")
            console.print("[dim]Note: Use without --dry-run to see actual changes.[/dim]")
        else:
            if result.get("success", False):
                console.print(f"[green]✓ {result.get('message', 'File edited successfully')}[/green]")
                if result.get("backup_path"):
                    console.print(f"[dim]Backup created: {result['backup_path']}[/dim]")
            else:
                console.print(f"[red]✗ {result.get('message', 'Failed to edit file')}[/red]")
                if result.get("backup_path"):
                    console.print(f"[dim]Backup available: {result['backup_path']}[/dim]")
                
    except Exception as e:
        console.print(f"[red]Error editing file: {e}[/red]")
        logger.exception("File edit error")


def _handle_file_create(editor: CodeEditor, prompt: str, file_path: str, language: Optional[str], dry_run: bool) -> None:
    """Handle file creation operations."""
    console.print(f"[bold]Creating file:[/bold] {file_path}")
    
    try:
        # Determine language if not specified
        if not language:
            path = Path(file_path)
            language = editor.get_language_from_extension(path.suffix)
        
        # Generate code
        generated_code = editor.generate_code(prompt, language)
        
        if dry_run:
            console.print(f"[bold]Proposed content:[/bold]")
            console.print(generated_code)
        else:
            # Write the file
            if editor.write_file(file_path, generated_code):
                console.print("[green]File created successfully.[/green]")
            else:
                console.print("[red]Failed to create file.[/red]")
                
    except Exception as e:
        console.print(f"[red]Error creating file: {e}[/red]")


def _handle_code_explanation(editor: CodeEditor, prompt: str, dry_run: bool) -> None:
    """Handle code explanation operations."""
    console.print("[bold]Code Explanation:[/bold]\n")
    
    # Try to extract code from prompt
    code_to_explain = ""
    
    # Check if prompt contains code directly or references a file
    if os.path.exists(prompt.strip()):
        # User provided a file path
        try:
            code_to_explain, _ = editor.read_file(prompt.strip())
            console.print(f"[dim]Explaining code from file: {prompt}[/dim]\n")
        except Exception as e:
            console.print(f"[red]Error reading file: {e}[/red]")
            return
    elif ":" in prompt:
        # Assume format is "explain this code: [code]"
        parts = prompt.split(":", 1)
        if len(parts) > 1:
            code_to_explain = parts[1].strip()
    else:
        # Check if there's a file path in the prompt
        words = prompt.split()
        for word in words:
            if os.path.exists(word):
                try:
                    code_to_explain, _ = editor.read_file(word)
                    break
                except:
                    pass
        
        # If no file found, treat the prompt as code
        if not code_to_explain:
            code_to_explain = prompt.replace("explain", "", 1).replace("this", "", 1).replace("code", "", 1).strip()
    
    # If we couldn't extract code, prompt the user
    if not code_to_explain or len(code_to_explain.strip()) < 10:
        console.print("[yellow]Please provide the code to explain.[/yellow]")
        console.print("[dim]You can:[/dim]")
        console.print("[dim]  1. Provide code directly: 'explain this code: def foo(): pass'[/dim]")
        console.print("[dim]  2. Provide a file path: 'explain this code: src/main.py'[/dim]")
        
        # Try to get code from user input
        user_code = typer.prompt("\nEnter code or file path", default="")
        if user_code:
            if os.path.exists(user_code):
                try:
                    code_to_explain, _ = editor.read_file(user_code)
                except Exception as e:
                    console.print(f"[red]Error reading file: {e}[/red]")
                    return
            else:
                code_to_explain = user_code
    
    if not code_to_explain:
        console.print("[red]No code provided.[/red]")
        return
    
    # Ask for detail level
    detail_level = typer.prompt("Detail level (low/medium/high)", default="medium")
    
    # Use the editor to explain the code
    console.print("[dim]Generating explanation...[/dim]\n")
    explanation = editor._core.explain_code(code_to_explain, detail_level)
    
    console.print("[bold]Explanation:[/bold]\n")
    console.print(explanation)


def _handle_code_debugging(editor: CodeEditor, prompt: str, dry_run: bool) -> None:
    """Handle code debugging operations."""
    console.print("[bold]Code Debugging:[/bold]\n")
    
    # Extract code and error from prompt
    code_to_debug = ""
    error_message = ""
    
    # Try to extract error message and code from prompt
    prompt_lower = prompt.lower()
    
    # Check for file path first
    words = prompt.split()
    for word in words:
        if os.path.exists(word):
            try:
                code_to_debug, _ = editor.read_file(word)
                console.print(f"[dim]Reading code from file: {word}[/dim]\n")
                break
            except Exception as e:
                console.print(f"[yellow]Could not read file {word}: {e}[/yellow]")
    
    # If no file found, try to extract from prompt
    if not code_to_debug:
        if "error:" in prompt_lower or "exception:" in prompt_lower:
            # Format: "debug error: [error] in [code]"
            separator = "error:" if "error:" in prompt_lower else "exception:"
            parts = prompt.split(separator, 1)
            if len(parts) > 1:
                remainder = parts[1].strip()
                if "in" in remainder:
                    error_parts = remainder.split("in", 1)
                    error_message = error_parts[0].strip()
                    code_to_debug = error_parts[1].strip()
                else:
                    error_message = remainder
        elif ":" in prompt:
            # Format: "debug: [code]"
            parts = prompt.split(":", 1)
            if len(parts) > 1:
                code_to_debug = parts[1].strip()
    
    # Prompt for missing information
    if not error_message:
        error_message = typer.prompt("Enter the error message (or press Enter to skip)", default="")
    
    if not code_to_debug or len(code_to_debug.strip()) < 10:
        console.print("[yellow]Code not found in prompt.[/yellow]")
        code_input = typer.prompt("Enter code or file path to debug", default="")
        if code_input:
            if os.path.exists(code_input):
                try:
                    code_to_debug, _ = editor.read_file(code_input)
                except Exception as e:
                    console.print(f"[red]Error reading file: {e}[/red]")
                    return
            else:
                code_to_debug = code_input
    
    if not code_to_debug:
        console.print("[red]No code provided for debugging.[/red]")
        return
    
    # Use the core debug_code method
    console.print("[dim]Analyzing code...[/dim]\n")
    debug_report = editor._core.debug_code(code_to_debug, error_message)
    
    # Display the debugging report
    console.print(f"[bold]Error Type:[/bold] {debug_report.error_type}")
    console.print(f"[bold]Error Message:[/bold] {debug_report.error_message}\n")
    
    if debug_report.suggestions:
        console.print("[bold]Suggestions:[/bold]")
        for i, suggestion in enumerate(debug_report.suggestions, 1):
            console.print(f"  {i}. {suggestion}")
    
    if debug_report.code_snippets:
        console.print("\n[bold]Suggested Code Fixes:[/bold]")
        for i, snippet in enumerate(debug_report.code_snippets, 1):
            console.print(f"\n[bold]Fix {i}:[/bold]")
            console.print(f"[code]{snippet}[/code]")


def _handle_code_refactoring(editor: CodeEditor, prompt: str, dry_run: bool) -> None:
    """Handle code refactoring operations."""
    console.print("[bold]Code Refactoring:[/bold]\n")
    
    # Extract refactoring goal and code from prompt
    refactoring_goal = ""
    code_to_refactor = ""
    language = "python"  # Default
    
    prompt_lower = prompt.lower()
    
    # Extract refactoring goal
    action_words = ["refactor", "optimize", "improve", "simplify"]
    for word in action_words:
        if word in prompt_lower:
            parts = prompt.split(word, 1)
            if len(parts) > 1:
                remainder = parts[1].strip()
                # Check if there's a "to" or "for" that separates goal from code
                if " to " in remainder.lower() or " for " in remainder.lower():
                    import re
                    goal_match = re.search(r'^(.*?)(?:\s+to\s+|\s+for\s+)(.+)$', remainder, re.IGNORECASE)
                    if goal_match:
                        refactoring_goal = goal_match.group(2).strip()
                        potential_code = goal_match.group(1).strip()
                        if len(potential_code) > 20:  # Likely code
                            code_to_refactor = potential_code
                    else:
                        refactoring_goal = remainder
                else:
                    refactoring_goal = remainder
                break
    
    # Check for file path in prompt
    words = prompt.split()
    for word in words:
        if os.path.exists(word):
            try:
                code_to_refactor, detected_language = editor.read_file(word)
                language = detected_language
                console.print(f"[dim]Reading code from file: {word}[/dim]\n")
                break
            except Exception as e:
                console.print(f"[yellow]Could not read file {word}: {e}[/yellow]")
    
    # If no file found, try to extract code from prompt
    if not code_to_refactor:
        if "code:" in prompt:
            parts = prompt.split("code:", 1)
            if len(parts) > 1:
                code_to_refactor = parts[1].strip()
        elif len(prompt) > 100:  # Might be code embedded in prompt
            # Try to find code-like patterns
            import re
            code_pattern = r'(def\s+\w+|function\s+\w+|class\s+\w+)[\s\S]*$'
            match = re.search(code_pattern, prompt, re.IGNORECASE)
            if match:
                code_to_refactor = match.group(0)
    
    # Prompt for missing information
    if not refactoring_goal:
        refactoring_goal = typer.prompt("What should be improved? (e.g., 'performance', 'readability', 'simplify')", default="improve code quality")
    
    if not code_to_refactor or len(code_to_refactor.strip()) < 10:
        console.print("[yellow]Code not found in prompt.[/yellow]")
        code_input = typer.prompt("Enter code or file path to refactor", default="")
        if code_input:
            if os.path.exists(code_input):
                try:
                    code_to_refactor, detected_language = editor.read_file(code_input)
                    language = detected_language
                except Exception as e:
                    console.print(f"[red]Error reading file: {e}[/red]")
                    return
            else:
                code_to_refactor = code_input
    
    if not code_to_refactor:
        console.print("[red]No code provided for refactoring.[/red]")
        return
    
    # Determine language if not already set
    if not language or language == "text":
        path = Path(code_to_refactor) if os.path.exists(code_to_refactor) else None
        if path:
            language = editor.get_language_from_extension(path.suffix)
        else:
            language = "python"  # Default
    
    # Use the core refactor_code method
    console.print(f"[dim]Refactoring code ({refactoring_goal})...[/dim]\n")
    refactored_code = editor._core.refactor_code(code_to_refactor, refactoring_goal, {"language": language})
    
    if dry_run:
        console.print("[bold]Refactored code:[/bold]\n")
        console.print(refactored_code)
    else:
        console.print("[bold]Refactored code:[/bold]\n")
        console.print(refactored_code)
        
        if typer.confirm("\nSave refactored code to a file?"):
            default_filename = f"refactored_code.{_get_extension_for_language(language)}"
            filename = typer.prompt("Enter filename", default=default_filename)
            
            if editor.write_file(filename, refactored_code):
                console.print(f"[green]Refactored code saved to {filename}[/green]")
            else:
                console.print("[red]Failed to save refactored code.[/red]")


def _handle_code_generation(editor: CodeEditor, prompt: str, language: Optional[str], dry_run: bool) -> None:
    """Handle code generation operations."""
    console.print("[bold]Code Generation:[/bold]\n")
    
    # Determine language if not specified
    if not language:
        # Try to infer language from prompt
        prompt_lower = prompt.lower()
        if "python" in prompt_lower:
            language = "python"
        elif "javascript" in prompt_lower or "js" in prompt_lower:
            language = "javascript"
        elif "typescript" in prompt_lower or "ts" in prompt_lower:
            language = "typescript"
        elif "bash" in prompt_lower or "shell" in prompt_lower:
            language = "bash"
        else:
            language = typer.prompt("Programming language", default="python")
    
    # Use the core generate_code method (which already handles LLM)
    console.print(f"[dim]Generating {language} code...[/dim]\n")
    generated_code = editor._core.generate_code(prompt, language)
    
    if dry_run:
        console.print(f"[bold]Generated {language} code:[/bold]\n")
        console.print(generated_code)
    else:
        # Show the generated code and ask if user wants to save it
        console.print(f"[bold]Generated {language} code:[/bold]\n")
        console.print(generated_code)
        
        if typer.confirm("\nSave this code to a file?"):
            default_filename = f"generated_code.{_get_extension_for_language(language)}"
            filename = typer.prompt("Enter filename", default=default_filename)
            
            if editor.write_file(filename, generated_code):
                console.print(f"[green]Code saved to {filename}[/green]")
            else:
                console.print("[red]Failed to save code.[/red]")


def _get_extension_for_language(language: str) -> str:
    """Get file extension for a programming language."""
    extensions = {
        "python": "py",
        "javascript": "js",
        "typescript": "ts",
        "bash": "sh",
        "yaml": "yaml",
        "json": "json",
        "plain": "txt",
        "html": "html",
        "css": "css"
    }
    return extensions.get(language.lower(), "txt")


def start_interactive_mode(model: str, sandbox: bool = False, verbose: bool = False) -> None:
    """Start interactive chat mode."""
    global context_provider
    
    # Set logging level based on verbose mode
    if verbose:
        logging.getLogger().setLevel(logging.DEBUG)
        logging.getLogger('joshu').setLevel(logging.DEBUG)
        logger.setLevel(logging.DEBUG)
    else:
        logging.getLogger().setLevel(logging.WARNING)
        logging.getLogger('joshu').setLevel(logging.WARNING)
        logger.setLevel(logging.WARNING)
    
    # Get configuration manager
    from joshu.core.config import get_config_manager
    config_manager = get_config_manager()
    
    # Use configured auto_execute setting
    auto_execute = config_manager.get("auto_execute", False)
    
    # Check if enhanced interactive mode is enabled
    enhanced_interactive = config_manager.get("enhanced_interactive", True)
    
    if enhanced_interactive:
        try:
            from joshu.ui.interactive import start_interactive_mode
            start_interactive_mode(model, sandbox, verbose=verbose)
            return
        except ImportError:
            pass  # Fall back to basic mode if enhanced mode is not available
    
    start_basic_interactive_mode(model, sandbox, config_manager)


def start_basic_interactive_mode(model: str, sandbox: bool, config_manager) -> None:
    """Start basic interactive chat mode (backward compatibility)."""
    global context_provider
    
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
            
            # Check if this needs execution (conversational responses don't need confirmation)
            # Check the flag first
            needs_execution = getattr(translation, 'needs_execution', True)
            
            # SAFETY CHECK: Also check explanation and command format directly as backup
            explanation_lower = translation.explanation.lower()
            command_normalized = translation.command.replace('\\"', '"').replace("\\'", "'")
            
            # Conversational indicators in explanation
            conversational_keywords = [
                "conversational response", "direct response", "direct answer",
                "to user's query", "to user's question", "user's query", "user's question",
                "answering", "providing answer", "providing response"
            ]
            
            # Check if explanation indicates conversational
            is_conversational_explanation = any(keyword in explanation_lower for keyword in conversational_keywords)
            
            # Check if command is a long informational echo (conversational)
            is_conversational_command = (
                '"""' in command_normalized or
                (command_normalized.startswith('echo "') and len(translation.command) > 100)
            )
            
            # Override needs_execution if we detect conversational response
            if is_conversational_explanation or is_conversational_command:
                needs_execution = False
            
            if not needs_execution:
                # This is a conversational response - execute it directly without asking
                code, out, err = run_command(translation.command)
                if code == 0:
                    if out:
                        console.print(out)
                else:
                    if err:
                        console.print(f"[red]{err}[/red]")
                continue
            
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
    """Main entry point."""
    import sys
    
    # If no arguments or first argument is not a command, treat as prompt
    if len(sys.argv) > 1:
        first_arg = sys.argv[1]
        # List of known commands
        known_commands = ["config", "run", "history", "repeat-last", "explain-last", "examples", "commands", "explain", "code", "--help", "-h", "--version", "-v"]
        
        # If first argument is not a known command, treat all arguments as a prompt
        if first_arg not in known_commands and not first_arg.startswith("-"):
            # Join all arguments as a single prompt
            prompt = " ".join(sys.argv[1:])
            
            # Initialize
            load_dotenv()
            
            # Initialize configuration manager
            from joshu.core.config import get_config_manager
            config_manager = get_config_manager()
            
            # Set current model from configuration
            global _current_model, context_provider
            _current_model = config_manager.get("model", "llama-3-8b")
            
            # Initialize context provider
            context_provider = ContextProvider()
            
            # Set system information
            from joshu.tools.system_info import get_detailed_system_info
            system_info = get_detailed_system_info()
            context_provider.set_system_info(system_info)
            
            print_banner(_current_model)
            
            # Execute the prompt directly
            try:
                execute_prompt(prompt)
            except Exception as e:
                console.print(f"[red]Error: {e}[/red]")
                sys.exit(1)
            
            sys.exit(0)
    
    # Otherwise, let Typer handle normally
    app()


if __name__ == "__main__":
    main()