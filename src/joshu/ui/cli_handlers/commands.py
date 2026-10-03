"""CLI command handlers."""

import os
import subprocess
from typing import Optional

import typer
from rich.console import Console

from joshu.core.context_provider import ContextProvider
from joshu.core.translate import translate_to_command

from .translation_helpers import display_safety_report, handle_translation_execution

console = Console()


def handle_config(
    list_config: bool, get: Optional[str], set: Optional[str], reset: bool, edit: bool
) -> None:
    """Handle configuration management."""
    from joshu.core.config import get_config_manager

    config_manager = get_config_manager()

    if list_config:
        console.print("[bold]Current Configuration:[/bold]")
        config_dict = config_manager.config.to_dict()
        for key, value in config_dict.items():
            console.print(f"  {key}: {value}")
        return

    if get:
        value = config_manager.get(get)
        if value is not None:
            console.print(f"{get}: {value}")
        else:
            console.print(f"[yellow]Configuration key '{get}' not found.[/yellow]")
        return

    if set:
        if "=" not in set:
            console.print("[red]Invalid format. Use key=value[/red]")
            raise typer.Exit(code=1)

        key, value = set.split("=", 1)

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
            console.print(f"[red]Invalid configuration key or value type: {key}={value!r}[/red]")
            raise typer.Exit(code=1)
        return

    if reset:
        config_manager.reset_to_defaults()
        config_manager.save_config()
        console.print("[green]Configuration reset to defaults.[/green]")
        return

    if edit:
        config_path = config_manager.get_config_path()
        if os.name == "nt":
            editor = os.environ.get("EDITOR", "notepad")
        else:
            editor = os.environ.get("EDITOR", "nano")

        try:
            subprocess.run([editor, str(config_path)])
            config_manager.load_config()
            console.print("[green]Configuration file edited and reloaded.[/green]")
        except Exception as e:
            console.print(f"[red]Failed to open editor: {e}[/red]")
            console.print(f"[yellow]You can manually edit: {config_path}[/yellow]")
        return

    console.print("[bold]Joshu Configuration Manager[/bold]")
    console.print("Use --help for more information.")


def handle_history(limit: int, context_provider: Optional[ContextProvider] = None) -> None:
    """Show command execution history."""
    from pathlib import Path

    from joshu.core.storage import EntryType, JsonFileStorage, QueryFilter

    # Try to get history from context provider first
    if context_provider and context_provider.conversation_context.messages:
        history_messages = context_provider.conversation_context.messages
        user_commands = [msg for msg in history_messages if msg["role"] == "user"]

        if user_commands:
            user_commands = user_commands[-limit:]
            console.print(f"[bold]Command History (last {len(user_commands)} entries):[/bold]")
            for i, msg in enumerate(user_commands, 1):
                console.print(f"  {i}. {msg['content']}")
            return

    # Fallback: Read from JSON storage
    try:
        storage = JsonFileStorage(Path.cwd() / "cache" / "joshu_data.json")
        filter = QueryFilter(entry_type=EntryType.CONVERSATION, role="user", limit=limit)
        entries = storage.query_entries(filter)

        if not entries:
            console.print("[yellow]No command history available.[/yellow]")
            return

        console.print(f"[bold]Command History (last {len(entries)} entries):[/bold]")
        for i, entry in enumerate(entries, 1):
            content = entry.data.get("content", "")
            console.print(f"  {i}. {content}")

    except Exception as e:
        console.print(f"[red]Error reading history from storage: {e}[/red]")
        console.print("[yellow]No history available.[/yellow]")


def handle_repeat_last(context_provider: Optional[ContextProvider] = None) -> None:
    """Repeat the last executed command."""
    if context_provider is None:
        context_provider = ContextProvider()

    from joshu.core.config import get_config_manager

    config_manager = get_config_manager()

    model = config_manager.get("model", "llama-3-8b")
    sandbox = config_manager.get("sandbox_enabled", True)
    auto_execute = config_manager.get("auto_execute", False)

    history_messages = context_provider.conversation_context.messages

    if not history_messages:
        console.print("[yellow]No history available to repeat.[/yellow]")
        raise typer.Exit(code=1)

    last_command = None
    for msg in reversed(history_messages):
        if msg["role"] == "user":
            last_command = msg["content"]
            break

    if not last_command:
        console.print("[yellow]No previous command found to repeat.[/yellow]")
        raise typer.Exit(code=1)

    console.print(f"[bold]Repeating last command:[/bold] {last_command}")

    translation = translate_to_command(last_command, context_provider, model)

    if not translation:
        console.print("[yellow]No translation found for the last command.[/yellow]")
        raise typer.Exit(code=2)

    console.print(f"[bold]Proposed command:[/bold] [cyan]{translation.command}[/cyan]")
    console.print(f"[dim]{translation.explanation}[/dim]\n")

    from joshu.core.safety import assess_command_safety

    report = assess_command_safety(translation.command, sandbox)

    if not report.safe:
        display_safety_report(report)
        raise typer.Exit(code=3)

    exit_code = handle_translation_execution(
        translation, last_command, sandbox, auto_execute, context_provider
    )
    raise typer.Exit(code=exit_code)


def handle_explain_last(context_provider: Optional[ContextProvider] = None) -> None:
    """Explain the last executed command."""
    if context_provider is None:
        context_provider = ContextProvider()

    history_messages = context_provider.conversation_context.messages

    if not history_messages:
        console.print("[yellow]No history available to explain.[/yellow]")
        raise typer.Exit(code=1)

    last_user_command = None
    last_assistant_response = None

    for i in range(len(history_messages) - 1, -1, -1):
        msg = history_messages[i]
        if msg["role"] == "assistant" and not last_assistant_response:
            last_assistant_response = msg["content"]
        elif msg["role"] == "user" and not last_user_command:
            last_user_command = msg["content"]

        if last_user_command and last_assistant_response:
            break

    if not last_user_command or not last_assistant_response:
        console.print("[yellow]No complete command history found to explain.[/yellow]")
        raise typer.Exit(code=1)

    console.print(f"[bold]Last Command:[/bold] {last_user_command}")
    console.print(f"[bold]Explanation:[/bold] {last_assistant_response}")


def handle_examples() -> None:
    """Show usage examples."""
    console.print("[bold]Joshu Usage Examples[/bold]\n")

    console.print("[cyan]Basic Commands:[/cyan]")
    console.print('  joshu "list all python files modified in the last week"')
    console.print('  joshu "create a backup of my project directory"')
    console.print('  joshu "show me memory usage of running processes"\n')

    console.print("[cyan]File System Intelligence:[/cyan]")
    console.print('  joshu "show me the structure of this project"')
    console.print('  joshu "find configuration files"')
    console.print('  joshu "what\'s in the log directory?"')
    console.print('  joshu "backup my source code"\n')

    console.print("[cyan]Code Generation:[/cyan]")
    console.print('  joshu "write a python function to parse CSV files"')
    console.print('  joshu "debug this bash script: ./deploy.sh"')
    console.print('  joshu "explain what this regex does: ^[a-zA-Z0-9+_.-]+@[a-zA-Z0-9.-]+$"\n')

    console.print("[cyan]Interactive Mode:[/cyan]")
    console.print("  joshu --interactive\n")

    console.print("[cyan]Safety Features:[/cyan]")
    console.print('  joshu "delete all files in /home"  # Will be blocked for safety')
    console.print('  joshu --sandbox "delete all files"  # Sandbox mode for testing\n')

    console.print("[cyan]Configuration:[/cyan]")
    console.print("  joshu config --list")
    console.print("  joshu config --set auto_execute=true")
    console.print("  joshu config --edit\n")


def handle_commands_list(category: Optional[str]) -> None:
    """Show available command categories and examples."""
    console.print("[bold]Joshu Command Categories[/bold]\n")

    if category is None:
        console.print("[cyan]Available Categories:[/cyan]")
        console.print("  file      - File system operations")
        console.print("  system    - System information and management")
        console.print("  network   - Network operations")
        console.print("  process   - Process management")
        console.print("  security  - Security-related commands")
        console.print("  git       - Git version control")
        console.print("  docker    - Docker container management")
        console.print(
            "\nUse 'joshu --commands [category]' to see examples for a specific category.\n"
        )
        return

    category = category.lower()
    categories = {
        "file": """[bold]File System Commands:[/bold]
  List files:                    joshu "list all files in current directory"
  Find files:                    joshu "find all python files"
  Show directory structure:      joshu "show me the structure of this project"
  Check disk usage:              joshu "show disk usage of current directory"
  Find large files:              joshu "find large files over 100MB"
  Backup files:                  joshu "backup my source code\"""",
        "system": """[bold]System Commands:[/bold]
  System information:            joshu "show system information"
  Memory usage:                  joshu "show memory usage"
  CPU information:               joshu "show CPU information"
  Network interfaces:            joshu "list network interfaces"
  Running processes:             joshu "show running processes\"""",
        "network": """[bold]Network Commands:[/bold]
  Check connectivity:            joshu "check if google.com is reachable"
  Port scanning:                 joshu "scan open ports on localhost"
  Download file:                 joshu "download https://example.com/file.txt"
  Check IP address:              joshu "what is my IP address\"""",
        "process": """[bold]Process Management Commands:[/bold]
  List processes:                joshu "show running processes"
  Kill process:                  joshu "kill process named python"
  Monitor process:               joshu "monitor process with PID 1234\"""",
        "security": """[bold]Security Commands:[/bold]
  Check file permissions:        joshu "check permissions of config.yaml"
  Generate password:             joshu "generate a secure password"
  Check open ports:              joshu "list open network ports\"""",
        "git": """[bold]Git Commands:[/bold]
  Git status:                    joshu "show git status"
  Git commit:                    joshu "commit changes with message 'Update README'"
  Git push:                      joshu "push changes to remote repository"
  Git branch:                    joshu "create new branch feature/new-feature\"""",
        "docker": """[bold]Docker Commands:[/bold]
  List containers:               joshu "list running docker containers"
  Start container:               joshu "start container named my-app"
  Stop container:                joshu "stop container with ID abc123"
  Build image:                   joshu "build docker image from Dockerfile\"""",
    }

    if category in categories:
        console.print(categories[category])
    else:
        console.print(f"[yellow]Unknown category: {category}[/yellow]")
        console.print("[cyan]Available Categories:[/cyan]")
        console.print("  file, system, network, process, security, git, docker")


def handle_explain(command: str, context_provider: Optional[ContextProvider] = None) -> None:
    """Explain a specific command or topic."""
    from joshu.core.config import get_config_manager

    config_manager = get_config_manager()
    model = config_manager.get("model", "llama-3-8b")

    prompt = f"Explain the '{command}' command in a clear and concise way. Include common usage examples and important options."

    translation = translate_to_command(prompt, context_provider, model)

    if translation and translation.command.startswith("echo"):
        import re

        match = re.search(r'echo\s+["\']{3}(.*?)["\']{3}', translation.command, re.DOTALL)
        if match:
            explanation = match.group(1)
            console.print(f"[bold]Explanation of '{command}':[/bold]\n{explanation}")
            return

    # Fallback: Try to get explanation from EchoProvider if available
    try:
        from joshu.models.providers import EchoProvider

        echo_provider = EchoProvider()
        explanation = echo_provider._generate_explanation_for_command(command)
        if explanation and explanation != f"Execute command: {command}":
            console.print(f"[bold]Explanation of '{command}':[/bold]\n{explanation}")
            return
    except Exception:
        pass  # Fall through to generic message

    # Final fallback: Generic message
    console.print(f"[bold]Explanation of '{command}':[/bold]")
    console.print(f"[yellow]No detailed explanation available for '{command}'.[/yellow]")
    console.print(
        "Try asking about common commands like: tar, git, docker, ls, grep, mkdir, cd, etc."
    )
