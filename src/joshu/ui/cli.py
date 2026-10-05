"""Main CLI entry point for Joshu."""

from __future__ import annotations

import sys
from typing import Any, Dict, List, Optional, Sequence

import typer
from rich.console import Console

# Import modular handlers
from .cli_handlers.commands import (
    handle_commands_list,
    handle_config,
    handle_examples,
    handle_history,
)
from .cli_handlers.init import initialize_context, setup_logging
from .cli_handlers.mcp_handler import (
    mcp_add,
    mcp_connect,
    mcp_disconnect,
    mcp_discover,
    mcp_list,
    mcp_remove,
    mcp_status,
)
from .cli_handlers.search_handler import handle_search_command
from .display import print_banner
from .interactive import start_interactive_mode

# Initialize app and console
app = typer.Typer(no_args_is_help=True)
mcp_app = typer.Typer(help="Manage MCP server integrations.")
app.add_typer(mcp_app, name="mcp")

from .cli_models import models_app, providers_app, use  # noqa: E402
from .cli_skills import skills_app  # noqa: E402

app.add_typer(providers_app, name="providers")
app.add_typer(models_app, name="models")
app.add_typer(skills_app, name="skills")
app.command(name="use")(use)
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


BANNER_COMMANDS = {"interactive", "explain"}


@app.callback()
def main_callback(
    ctx: typer.Context,
    version: Optional[bool] = typer.Option(
        None,
        "--version",
        "-v",
        callback=version_callback,
        is_eager=True,
        help="Show version and exit.",
    ),
) -> None:
    """Joshu - Natural language meets your terminal."""
    global context_provider, _current_model

    config_manager, context_provider, _current_model = initialize_context()
    # Only commands that start a conversation show the banner; `run` prints it
    # itself (headless runs print only the result), and commands like
    # `models` or `config` print just their output
    if ctx.invoked_subcommand in BANNER_COMMANDS:
        print_banner(_current_model)


def run_stream_json(
    prompt: Optional[str],
    model: Optional[str],
    provider: Optional[str],
    permission_mode: Optional[str],
    input_format: str,
    resume: Optional[str],
    continue_last: bool,
    images: Sequence[str] = (),
) -> int:
    """
    Run requests and print events as JSON lines (see joshu.sdk for the event types).

    With input_format "stream-json", requests are read from stdin, one JSON
    object per line ({"type": "user", "content": "..."}); otherwise `prompt`
    is the single request.
    """
    import json

    from joshu.core.config import get_config_manager
    from joshu.core.llm_client import LLMError
    from joshu.core.sessions import SessionError
    from joshu.sdk import Session

    def emit(event: Dict[str, Any]) -> None:
        sys.stdout.write(json.dumps(event, ensure_ascii=False, default=str) + "\n")
        sys.stdout.flush()

    if input_format not in ("text", "stream-json"):
        emit({"type": "error", "message": f"Unknown input format '{input_format}'"})
        return 2
    if input_format != "stream-json" and not prompt:
        emit(
            {"type": "error", "message": "A prompt is required (or use --input-format stream-json)"}
        )
        return 2

    config = get_config_manager()
    try:
        session = Session(
            model=model,
            provider=provider,
            permission_mode=permission_mode or config.get("permission_mode", "default"),
            on_event=emit,
            load_mcp=True,
            persist=config.get("save_sessions", True),
            resume=resume or ("last" if continue_last else None),
        )
    except (LLMError, SessionError, ValueError) as e:
        emit({"type": "error", "message": str(e)})
        return 1

    emit(
        {
            "type": "system",
            "session_id": session.session_id,
            "model": getattr(session.agent.client, "model", None),
            "cwd": str(session.cwd),
            "tools": [spec.name for spec in session.agent.tool_specs()],
        }
    )

    def requests():
        if input_format != "stream-json":
            yield prompt
            return
        for line in sys.stdin:
            line = line.strip()
            if not line:
                continue
            try:
                message = json.loads(line)
            except ValueError:
                yield line  # plain text line
                continue
            if isinstance(message, str):
                yield message
            elif isinstance(message, dict):
                content = message.get("content", message.get("prompt", ""))
                if isinstance(content, list):  # [{"type": "text", "text": ...}, ...]
                    content = " ".join(
                        part.get("text", "") for part in content if isinstance(part, dict)
                    )
                if str(content).strip():
                    yield str(content)

    code = 0
    try:
        for index, request in enumerate(requests()):
            try:
                session.send(request, images=images if index == 0 else ())
            except LLMError as e:
                emit({"type": "error", "message": str(e)})
                code = 1
    except KeyboardInterrupt:
        emit({"type": "error", "message": "interrupted"})
        code = 130
    finally:
        session.close()
    return code


def execute_agent_prompt(
    prompt: str,
    model: Optional[str],
    permission_mode: Optional[str],
    headless: bool,
    output_format: str,
    sandbox: bool,
    provider: Optional[str] = None,
    resume: Optional[str] = None,
    continue_last: bool = False,
    images: Sequence[str] = (),
) -> int:
    """
    Run a prompt through the tool-using agent.

    Returns:
        Exit code: 0 on success, 1 on model/config errors, 130 when interrupted.
    """
    import json

    from joshu.core.llm_client import LLMError
    from joshu.core.permissions import PermissionMode

    from .agent_ui import create_console_agent

    try:
        mode = PermissionMode.from_string(permission_mode) if permission_mode else None
    except ValueError as e:
        console.print(f"[red]{e}[/red]")
        return 2

    # Approvals need a person at the terminal
    can_ask = not headless and sys.stdin.isatty()
    agent = None
    ui = None
    try:
        agent, ui = create_console_agent(
            model=model,
            provider=provider,
            mode=mode,
            sandbox=sandbox,
            interactive=can_ask,
            quiet=headless,
        )
        if not _restore_session(agent, resume, continue_last):
            return 1
        if prompt.startswith("/"):
            from joshu.core.custom_commands import expand_slash_command

            expanded = expand_slash_command(prompt, agent.permissions)
            if expanded is None:
                Console(stderr=True).print(
                    f"[red]Unknown command {prompt.split()[0]}.[/red] "
                    "Custom commands live in .joshu/commands/ or ~/.joshu/commands/."
                )
                return 2
            prompt = expanded

        from pathlib import Path

        from joshu.core.file_refs import attach_file_refs
        from joshu.core.images import ImageError, find_image_refs, image_part
        from joshu.mcp.extras import with_resources

        prompt, referenced = find_image_refs(prompt)
        prompt = with_resources(prompt)
        prompt, _files = attach_file_refs(prompt)
        attached = [Path(p).expanduser() for p in images] + referenced
        try:
            for path in attached:
                image_part(path)  # validate before calling the model
        except ImageError as e:
            Console(stderr=True).print(f"[red]{e}[/red]")
            return 2
        ui.begin_request()
        response = agent.run(prompt, images=attached)
    except LLMError as e:
        Console(stderr=True).print(f"[red]Model error:[/red] {e}")
        return 1
    except KeyboardInterrupt:
        Console(stderr=True).print("\nInterrupted.")
        return 130
    finally:
        if ui is not None:
            ui.end_request()
        if agent is not None:
            agent.end_session()

    if output_format == "json":
        payload = {"result": response.text, **response.metadata}
        print(json.dumps(payload, ensure_ascii=False))
    elif headless:
        print(response.text)
    else:
        ui.print_footer(response)
    return 0


def _restore_session(agent, resume: Optional[str], continue_last: bool) -> bool:
    """
    Load a saved conversation into the agent, if one was requested.

    Returns False (after printing why) when the requested session can't be loaded.
    """
    from joshu.core.sessions import SessionError, latest_session, load_session

    err = Console(stderr=True)
    if resume:
        try:
            agent.restore(load_session(resume))
        except SessionError as e:
            err.print(f"[red]{e}[/red]")
            return False
    elif continue_last:
        latest = latest_session(agent.cwd)
        if latest is None:
            err.print("[yellow]No previous session in this directory; starting a new one.[/yellow]")
        else:
            agent.restore(load_session(latest.id))
    return True


@app.command()
def sessions(
    all_dirs: bool = typer.Option(
        False, "--all", "-a", help="Show sessions from every directory, not just this one."
    ),
    limit: int = typer.Option(20, "--limit", "-n", help="Number of sessions to show."),
) -> None:
    """List saved agent sessions (resume one with `joshu run --resume <id>`)."""
    from pathlib import Path

    from rich.table import Table

    from joshu.core.sessions import list_sessions

    infos = list_sessions(None if all_dirs else Path.cwd(), limit=limit)
    if not infos:
        where = "" if all_dirs else " in this directory (try --all)"
        console.print(f"[yellow]No saved sessions{where}.[/yellow]")
        return

    table = Table(title="Saved sessions")
    table.add_column("Id")
    table.add_column("Updated")
    table.add_column("Messages", justify="right")
    table.add_column("First request")
    if all_dirs:
        table.add_column("Directory")
    for info in infos:
        row = [info.id, info.updated_at.replace("T", " "), str(info.message_count), info.title]
        if all_dirs:
            row.append(info.cwd)
        table.add_row(*row)
    console.print(table)
    console.print(
        '[dim]Resume: joshu run --resume <id> "..."  or  joshu interactive --resume <id>[/dim]'
    )


@app.command()
def config(
    list_config: bool = typer.Option(False, "--list", "-l", help="List all configuration options."),
    get: Optional[str] = typer.Option(
        None, "--get", "-g", help="Get a specific configuration value."
    ),
    set: Optional[str] = typer.Option(
        None, "--set", "-s", help="Set a configuration value (format: key=value)."
    ),
    reset: bool = typer.Option(False, "--reset", "-r", help="Reset configuration to defaults."),
    edit: bool = typer.Option(False, "--edit", "-e", help="Open configuration file in editor."),
) -> None:
    """Manage Joshu configuration."""
    handle_config(list_config, get, set, reset, edit)


def _use_provider(provider: str, model: Optional[str]) -> str:
    """
    Switch provider for this process (the config file is not changed).

    Returns the model to use: the given one, else the provider's default.
    Exits with an error for an unknown provider or one without a default model.
    """
    from joshu.core.config import get_config_manager
    from joshu.core.providers import ProviderError, get_providers

    config_manager = get_config_manager()
    try:
        providers = get_providers(config_manager.get("providers") or {})
    except ProviderError as e:
        console.print(f"[red]Invalid provider configuration: {e}[/red]")
        raise typer.Exit(code=2)

    if provider not in providers:
        console.print(
            f"[red]Unknown provider '{provider}'.[/red] Run `joshu providers` to list them."
        )
        raise typer.Exit(code=2)

    model = model or providers[provider].default_model
    if not model:
        console.print(f"[red]Provider '{provider}' has no default model; pass --model.[/red]")
        raise typer.Exit(code=2)

    config_manager.set("provider", provider)
    config_manager.set("model", model)
    return model


@app.command()
def interactive(
    model: str = typer.Option(None, "--model", "-m", help="LLM model to use."),
    sandbox: bool = typer.Option(
        None,
        "--sandbox",
        "-s",
        help="Enable sandbox mode for testing (blocks all destructive commands).",
    ),
    verbose: bool = typer.Option(
        False, "--verbose", "-v", help="Enable verbose output (show debug logs)."
    ),
    provider: Optional[str] = typer.Option(
        None,
        "--provider",
        help="Model provider (see `joshu providers`); overrides the config for this run.",
    ),
    resume: Optional[str] = typer.Option(
        None, "--resume", help="Continue a saved session by id (see `joshu sessions`)."
    ),
    continue_last: bool = typer.Option(
        False, "--continue", "-c", help="Continue the most recent session in this directory."
    ),
) -> None:
    """Start interactive chat mode directly."""
    _start_interactive(model, sandbox, verbose, provider, resume, continue_last)


def _start_interactive(
    model: Optional[str],
    sandbox: Optional[bool],
    verbose: bool,
    provider: Optional[str],
    resume: Optional[str] = None,
    continue_last: bool = False,
) -> None:
    """Start the interactive REPL with CLI overrides applied."""
    global _current_model

    from joshu.core.config import get_config_manager

    config_manager = get_config_manager()

    if provider:
        model = _use_provider(provider, model)
    if model is None:
        model = config_manager.get("model")
    _current_model = model

    if sandbox is None:
        sandbox = config_manager.get("sandbox_enabled", True)

    setup_logging(verbose)
    start_interactive_mode(
        model, sandbox, verbose=verbose, resume=resume, continue_last=continue_last
    )


@app.command()
def run(
    prompt: Optional[str] = typer.Argument(None, help="Instruction or task to execute."),
    interactive: bool = typer.Option(
        False, "--interactive", "-i", help="Start interactive chat mode."
    ),
    yes: bool = typer.Option(
        False,
        "--yes",
        "-y",
        help="Run tools without asking (bypass mode); commands flagged unsafe still ask.",
    ),
    model: str = typer.Option(None, "--model", "-m", help="LLM model to use."),
    sandbox: bool = typer.Option(
        None,
        "--sandbox",
        "-s",
        help="Enable sandbox mode for testing (blocks all destructive commands).",
    ),
    verbose: bool = typer.Option(
        False, "--verbose", "-v", help="Enable verbose output (show debug logs)."
    ),
    permission_mode: Optional[str] = typer.Option(
        None,
        "--permission-mode",
        help="Agent permissions: default, accept_edits, plan (read-only) or bypass.",
    ),
    print_mode: bool = typer.Option(
        False,
        "--print",
        "-p",
        help="Headless: print only the final answer; tools needing approval are denied.",
    ),
    output_format: str = typer.Option(
        "text",
        "--output-format",
        help="text, json, or stream-json (one JSON event per line as it happens); "
        "json and stream-json imply --print.",
    ),
    input_format: str = typer.Option(
        "text",
        "--input-format",
        help="text, or stream-json: read requests from stdin, one JSON line each "
        '({"type": "user", "content": "..."}), in one conversation.',
    ),
    provider: Optional[str] = typer.Option(
        None,
        "--provider",
        help="Model provider (see `joshu providers`); overrides the config for this run.",
    ),
    resume: Optional[str] = typer.Option(
        None, "--resume", help="Continue a saved session by id (see `joshu sessions`)."
    ),
    continue_last: bool = typer.Option(
        False, "--continue", "-c", help="Continue the most recent session in this directory."
    ),
    image: Optional[List[str]] = typer.Option(
        None,
        "--image",
        help="Attach an image (repeatable). @path/to/image.png in the prompt works too.",
    ),
) -> None:
    """Run a task with the agent, or start interactive mode."""
    streaming = "stream-json" in (output_format, input_format)
    headless = print_mode or output_format in ("json", "stream-json") or streaming
    if not headless:
        print_banner(_current_model)

    if interactive:
        _start_interactive(model, sandbox, verbose, provider, resume, continue_last)
        return

    if streaming:
        setup_logging(verbose)
        raise typer.Exit(
            code=run_stream_json(
                prompt,
                model=model,
                provider=provider,
                permission_mode=permission_mode or ("bypass" if yes else None),
                input_format=input_format,
                resume=resume,
                continue_last=continue_last,
                images=image or [],
            )
        )

    if not prompt:
        console.print("[red]Error: Prompt is required for non-interactive mode.[/red]")
        console.print("[dim]Use --interactive or -i for interactive mode without a prompt.[/dim]")
        raise typer.Exit(code=1)

    if output_format not in ("text", "json"):
        console.print(f"[red]Unknown output format '{output_format}'. Use text or json.[/red]")
        raise typer.Exit(code=2)

    from joshu.core.config import get_config_manager

    config_manager = get_config_manager()
    if sandbox is None:
        sandbox = config_manager.get("sandbox_enabled", True)
    if yes and permission_mode is None:
        permission_mode = "bypass"

    setup_logging(verbose)
    exit_code = execute_agent_prompt(
        prompt,
        model=model,
        permission_mode=permission_mode,
        headless=headless,
        output_format=output_format,
        sandbox=sandbox,
        provider=provider,
        resume=resume,
        continue_last=continue_last,
        images=image or [],
    )
    raise typer.Exit(code=exit_code)


@app.command()
def history(
    limit: int = typer.Option(10, "--limit", "-n", help="Number of history entries to show."),
) -> None:
    """Show command execution history."""
    global context_provider
    handle_history(limit, context_provider)


@app.command()
def examples() -> None:
    """Show usage examples for Joshu."""
    handle_examples()


@app.command()
def commands(
    category: str = typer.Argument(
        None, help="Category of commands to show (e.g., file, system, network)"
    ),
) -> None:
    """Show available command categories and examples."""
    handle_commands_list(category)


@app.command()
def explain(command: str = typer.Argument(..., help="Command or topic to explain")) -> None:
    """Explain a command or topic (read-only: nothing is run or changed)."""
    from joshu.core.config import get_config_manager

    exit_code = execute_agent_prompt(
        "Explain this command or topic clearly and concisely. If it is a shell command, "
        f"say what each part does and any risks: {command}",
        model=None,
        permission_mode="plan",
        headless=False,
        output_format="text",
        sandbox=get_config_manager().get("sandbox_enabled", True),
    )
    raise typer.Exit(code=exit_code)


@app.command()
def trust(
    path: Optional[str] = typer.Argument(None, help="Project directory (default: here)."),
    remove: bool = typer.Option(False, "--remove", help="Stop trusting the project."),
    list_trusted: bool = typer.Option(False, "--list", help="List trusted projects."),
) -> None:
    """Let a project's .joshu/config.yaml apply (it can run commands, so it needs trust)."""
    from pathlib import Path

    import yaml

    from joshu.core.config import PROJECT_CONFIG, get_config_manager

    config_manager = get_config_manager()
    if list_trusted:
        trusted = config_manager.get("trusted_projects") or []
        if not trusted:
            console.print("No trusted projects.")
        for project in trusted:
            console.print(f"  {project}")
        return

    directory = Path(path).expanduser().resolve() if path else Path.cwd().resolve()
    if remove:
        if config_manager.untrust_project(directory):
            config_manager.save_config()
            console.print(f"No longer trusted: {directory}")
        else:
            console.print(f"Not in the trusted list: {directory}")
        return

    project_config = directory / PROJECT_CONFIG
    if project_config.is_file():
        try:
            data = yaml.safe_load(project_config.read_text(encoding="utf-8")) or {}
        except Exception as e:
            console.print(f"[red]Can't read {project_config}: {e}[/red]")
            raise typer.Exit(code=1)
        keys = sorted(data) if isinstance(data, dict) else []
        console.print(f"{project_config} sets: {', '.join(keys) or '(nothing)'}")
        risky = [
            k
            for k in keys
            if k
            in (
                "hooks",
                "diagnostics",
                "providers",
                "shell_sandbox",
                "permission_mode",
                "permissions",
                "mcp_servers",
            )
        ]
        if risky:
            console.print(
                f"[yellow]Review these before trusting: {', '.join(risky)} "
                "(they can run commands or change what the agent may do)[/yellow]"
            )
    else:
        console.print(
            f"[dim]{project_config} doesn't exist yet; trusting the directory anyway.[/dim]"
        )

    config_manager.trust_project(directory)
    config_manager.save_config()
    console.print(f"Trusted: {directory}")


@app.command()
def serve(
    host: str = typer.Option("127.0.0.1", "--host", help="Address to listen on."),
    port: int = typer.Option(8080, "--port", help="Port to listen on."),
) -> None:
    """Run the A2A server so other agents and tools can give Joshu tasks over HTTP."""
    import os
    import secrets

    try:
        from joshu.a2a.server import run_server
    except ImportError:
        console.print("[red]The A2A server needs extra packages:[/red] pip install -e .[a2a]")
        raise typer.Exit(code=1)

    if not os.getenv("JOSHU_A2A_TOKEN"):
        os.environ["JOSHU_A2A_TOKEN"] = secrets.token_urlsafe(24)
    console.print(f"A2A server on http://{host}:{port}")
    console.print(
        f"Send this header with every request: Authorization: Bearer {os.environ['JOSHU_A2A_TOKEN']}"
    )
    if host not in ("127.0.0.1", "localhost", "::1"):
        console.print(
            "[yellow]Listening beyond this machine: anyone with the token can run tasks "
            "that edit files and run commands here.[/yellow]"
        )
    run_server(host, port)


@app.command()
def search(
    query: str = typer.Argument(..., help="Search query"),
    max_results: int = typer.Option(
        None, "--max-results", "-n", help="Maximum number of results to show"
    ),
) -> None:
    """Search the web for information."""
    handle_search_command(query, max_results)


# MCP Subcommands
@mcp_app.command("list")
def mcp_list_cmd() -> None:
    """List all configured MCP servers and their status."""
    mcp_list()


@mcp_app.command("add")
def mcp_add_cmd(
    name: str = typer.Argument(..., help="Unique name for the server"),
    command: Optional[str] = typer.Option(
        None, "--command", "-c", help="Command to run (for stdio transport)"
    ),
    url: Optional[str] = typer.Option(
        None, "--url", "-u", help="URL to connect (for http transport)"
    ),
    args: Optional[str] = typer.Option(
        None, "--args", "-a", help="Space-separated command arguments"
    ),
    transport: str = typer.Option(
        "stdio", "--transport", "-t", help="Transport type (stdio, http)"
    ),
    disabled: bool = typer.Option(False, "--disabled", help="Add server as disabled"),
) -> None:
    """Add a new MCP server configuration."""
    mcp_add(name, command, url, args, transport, not disabled)


@mcp_app.command("remove")
def mcp_remove_cmd(
    name: str = typer.Argument(..., help="Name of the server to remove"),
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation prompt"),
) -> None:
    """Remove an MCP server configuration."""
    mcp_remove(name, force)


@mcp_app.command("status")
def mcp_status_cmd(
    name: Optional[str] = typer.Argument(None, help="Specific server name"),
) -> None:
    """Show detailed status of MCP servers."""
    mcp_status(name)


@mcp_app.command("connect")
def mcp_connect_cmd(
    name: Optional[str] = typer.Argument(None, help="Server name, or all if not specified"),
) -> None:
    """Connect to MCP server(s)."""
    mcp_connect(name)


@mcp_app.command("disconnect")
def mcp_disconnect_cmd(
    name: Optional[str] = typer.Argument(None, help="Server name, or all if not specified"),
) -> None:
    """Disconnect from MCP server(s)."""
    mcp_disconnect(name)


@mcp_app.command("discover")
def mcp_discover_cmd() -> None:
    """Discover and list tools from all connected MCP servers."""
    mcp_discover()


def _ensure_utf8_output() -> None:
    """
    Use UTF-8 for stdout/stderr when the console encoding can't print Unicode.

    Windows consoles and pipes often default to cp1252, which crashes on the
    banner and status symbols; unencodable characters are replaced instead.
    """
    for stream in (sys.stdout, sys.stderr):
        encoding = (getattr(stream, "encoding", None) or "").lower().replace("-", "")
        if encoding != "utf8" and hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8", errors="replace")
            except (ValueError, OSError):
                pass


def subcommand_names() -> set:
    """Names `joshu <name>` treats as a command; any other first word starts a task."""
    names = {"--help", "-h", "--version", "-v"}
    for command in app.registered_commands:
        name = command.name or getattr(command.callback, "__name__", "")
        names.add(name.replace("_", "-"))
    names.update(group.name for group in app.registered_groups if group.name)
    return names


def main() -> None:
    """Main entry point."""
    _ensure_utf8_output()
    # Plain `joshu` starts a conversation (`joshu --help` lists the commands)
    if len(sys.argv) == 1:
        sys.argv.append("interactive")
    if len(sys.argv) > 1:
        first_arg = sys.argv[1]
        if first_arg not in SUBCOMMANDS and not first_arg.startswith("-"):
            prompt = " ".join(sys.argv[1:])

            global context_provider, _current_model
            config_manager, context_provider, _current_model = initialize_context()
            print_banner(_current_model)

            sys.exit(
                execute_agent_prompt(
                    prompt,
                    model=None,
                    permission_mode=None,
                    headless=False,
                    output_format="text",
                    sandbox=config_manager.get("sandbox_enabled", True),
                )
            )

    app()


# Every command is registered by now (main() may run with `app` swapped out in tests)
SUBCOMMANDS = subcommand_names()


if __name__ == "__main__":
    main()
