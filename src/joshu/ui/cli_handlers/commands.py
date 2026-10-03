"""CLI command handlers."""

import os
import subprocess
from typing import Optional

import typer
from rich.console import Console

from joshu.core.context_provider import ContextProvider

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
    """Show your most recent requests to the agent in this directory."""
    from pathlib import Path

    from joshu.core.sessions import recent_prompts

    prompts = recent_prompts(Path.cwd(), limit=limit)
    if not prompts:
        console.print("[yellow]No saved requests in this directory.[/yellow]")
        return

    console.print(f"[bold]Recent requests (last {len(prompts)}):[/bold]")
    for i, (session_id, text) in enumerate(prompts, 1):
        first_line = text.strip().splitlines()[0] if text.strip() else ""
        console.print(f"  {i}. {first_line}  [dim]({session_id})[/dim]")
    console.print('[dim]Continue one with: joshu run --resume <session id> "..."[/dim]')


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
    console.print('  joshu run --sandbox "delete all files"  # Sandbox mode for testing\n')

    console.print("[cyan]Configuration:[/cyan]")
    console.print("  joshu config --list")
    console.print("  joshu config --set permission_mode=accept_edits")
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
