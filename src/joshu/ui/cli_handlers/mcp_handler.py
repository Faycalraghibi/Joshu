"""
MCP CLI Command Handlers.

Provides CLI commands for managing MCP server integrations.
"""

from __future__ import annotations

import logging
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from joshu.core.config import get_config_manager
from joshu.mcp.loop import run as run_on_mcp_loop

logger = logging.getLogger(__name__)
console = Console()


def mcp_list() -> None:
    """
    List all configured MCP servers and their status.
    """
    from joshu.mcp.registry import get_mcp_registry

    # Auto-load servers from config files
    load_mcp_servers_from_config()

    registry = get_mcp_registry()
    servers = registry.list_servers()

    if not servers:
        console.print("[yellow]No MCP servers configured.[/yellow]")
        console.print("\nTo add a server, use:")
        console.print("  [cyan]joshu mcp add <name> --command <cmd>[/cyan]")
        console.print("  [cyan]joshu mcp add <name> --url <url>[/cyan]")
        console.print("\nOr create a [cyan]config/mcp.json[/cyan] file with:")
        console.print('  {"mcpServers": {"name": {"command": "...", "args": [...]}}}')
        return

    # Create table
    table = Table(title="MCP Servers")
    table.add_column("Name", style="cyan")
    table.add_column("Transport", style="magenta")
    table.add_column("Status", style="green")
    table.add_column("Enabled", style="yellow")
    table.add_column("Command/URL", style="dim")

    for server in servers:
        connected = registry.is_connected(server.name)
        status = "[green]Connected[/green]" if connected else "[dim]Disconnected[/dim]"
        enabled = "✓" if server.enabled else "✗"

        location = server.command if server.command else server.url or "-"
        if len(str(location)) > 40:
            location = str(location)[:37] + "..."

        table.add_row(
            server.name,
            server.transport.value,
            status,
            enabled,
            str(location),
        )

    console.print(table)

    # Show summary
    connected_count = sum(1 for s in servers if registry.is_connected(s.name))
    console.print(f"\n[dim]Total: {len(servers)} servers, {connected_count} connected[/dim]")


def mcp_add(
    name: str,
    command: Optional[str] = None,
    url: Optional[str] = None,
    args: Optional[str] = None,
    transport: str = "stdio",
    enabled: bool = True,
) -> None:
    """
    Add a new MCP server configuration.

    Args:
        name: Unique name for the server.
        command: Command to run (for stdio transport).
        url: URL to connect (for http transport).
        args: Space-separated command arguments.
        transport: Transport type (stdio, http).
        enabled: Whether server is enabled.
    """
    from joshu.mcp.registry import get_mcp_registry
    from joshu.mcp.schemas import MCPServerConfig, TransportType

    if not command and not url:
        console.print("[red]Error: Must specify --command or --url[/red]")
        raise typer.Exit(1)

    try:
        transport_type = TransportType(transport)
    except ValueError:
        console.print(f"[red]Error: Invalid transport '{transport}'. Use 'stdio' or 'http'.[/red]")
        raise typer.Exit(1)

    # Parse args
    args_list = args.split() if args else []

    # Create config
    config = MCPServerConfig(
        name=name,
        transport=transport_type,
        command=command,
        url=url,
        args=args_list,
        enabled=enabled,
    )

    if not config.validate():
        console.print("[red]Error: Invalid configuration[/red]")
        if transport_type == TransportType.STDIO and not command:
            console.print("[yellow]Stdio transport requires --command[/yellow]")
        elif transport_type == TransportType.HTTP and not url:
            console.print("[yellow]HTTP transport requires --url[/yellow]")
        raise typer.Exit(1)

    # Add to registry
    registry = get_mcp_registry()
    registry.add_server(config)

    # Save to config file
    config_manager = get_config_manager()
    mcp_servers = config_manager.get("mcp_servers", {}) or {}
    mcp_servers[name] = config.to_dict()
    config_manager.set("mcp_servers", mcp_servers)
    config_manager.save_config()

    console.print(f"[green]✓ Added MCP server: {name}[/green]")
    console.print(f"  Transport: {transport}")
    if command:
        console.print(f"  Command: {command}")
    if url:
        console.print(f"  URL: {url}")


def mcp_remove(name: str, force: bool = False) -> None:
    """
    Remove an MCP server configuration.

    Args:
        name: Name of the server to remove.
        force: Skip confirmation prompt.
    """
    from joshu.mcp.registry import get_mcp_registry

    registry = get_mcp_registry()

    if not registry.get_server(name):
        console.print(f"[red]Error: Server '{name}' not found[/red]")
        raise typer.Exit(1)

    if not force:
        confirm = typer.confirm(f"Remove MCP server '{name}'?")
        if not confirm:
            console.print("[yellow]Cancelled[/yellow]")
            raise typer.Exit(0)

    # Remove from registry
    registry.remove_server(name)

    # Remove from config file
    config_manager = get_config_manager()
    mcp_servers = config_manager.get("mcp_servers", {}) or {}
    if name in mcp_servers:
        del mcp_servers[name]
        config_manager.set("mcp_servers", mcp_servers)
        config_manager.save_config()

    console.print(f"[green]✓ Removed MCP server: {name}[/green]")


def mcp_status(name: Optional[str] = None) -> None:
    """
    Show detailed status of MCP servers.

    Args:
        name: Optional specific server name.
    """
    from joshu.mcp.registry import get_mcp_registry

    registry = get_mcp_registry()

    if name:
        server = registry.get_server(name)
        if not server:
            console.print(f"[red]Error: Server '{name}' not found[/red]")
            raise typer.Exit(1)

        _show_server_details(name, server, registry)
    else:
        status = registry.get_status()
        if not status:
            console.print("[yellow]No MCP servers configured.[/yellow]")
            return

        for server_name in status:
            server = registry.get_server(server_name)
            if server:
                _show_server_details(server_name, server, registry)
                console.print()


def _show_server_details(name: str, server, registry) -> None:
    """Show detailed information for a single server."""
    connected = registry.is_connected(name)

    console.print(f"[bold cyan]{name}[/bold cyan]")
    console.print(f"  Transport: {server.transport.value}")
    console.print(f"  Enabled: {'Yes' if server.enabled else 'No'}")
    console.print(f"  Connected: {'Yes' if connected else 'No'}")

    if server.command:
        console.print(f"  Command: {server.command}")
        if server.args:
            console.print(f"  Args: {' '.join(server.args)}")
    if server.url:
        console.print(f"  URL: {server.url}")

    if server.include_tools:
        console.print(f"  Include tools: {', '.join(server.include_tools)}")
    if server.exclude_tools:
        console.print(f"  Exclude tools: {', '.join(server.exclude_tools)}")

    # Show discovered tools if connected
    if connected:
        transport = registry.get_transport(name)
        if transport:
            try:
                tools = run_on_mcp_loop(transport.list_tools())
                console.print(f"  Tools ({len(tools)}):")
                for tool in tools[:5]:
                    console.print(f"    - {tool.name}")
                if len(tools) > 5:
                    console.print(f"    ... and {len(tools) - 5} more")
            except Exception as e:
                console.print(f"  [red]Error listing tools: {e}[/red]")


def mcp_connect(name: Optional[str] = None) -> None:
    """
    Connect to MCP server(s).

    Args:
        name: Specific server name, or None to connect all.
    """
    from joshu.mcp.registry import get_mcp_registry

    registry = get_mcp_registry()

    if name:
        if not registry.get_server(name):
            console.print(f"[red]Error: Server '{name}' not found[/red]")
            raise typer.Exit(1)

        try:
            success = run_on_mcp_loop(registry.connect_server(name))
            if success:
                console.print(f"[green]✓ Connected to {name}[/green]")
            else:
                console.print(f"[yellow]Could not connect to {name}[/yellow]")
        except Exception as e:
            console.print(f"[red]Error connecting to {name}: {e}[/red]")
            raise typer.Exit(1)
    else:
        console.print("Connecting to all enabled servers...")
        results = run_on_mcp_loop(registry.connect_all())
        for server_name, success in results.items():
            if success:
                console.print(f"  [green]✓ {server_name}[/green]")
            else:
                console.print(f"  [red]✗ {server_name}[/red]")


def mcp_disconnect(name: Optional[str] = None) -> None:
    """
    Disconnect from MCP server(s).

    Args:
        name: Specific server name, or None to disconnect all.
    """
    from joshu.mcp.registry import get_mcp_registry

    registry = get_mcp_registry()

    if name:
        success = run_on_mcp_loop(registry.disconnect_server(name))
        if success:
            console.print(f"[green]✓ Disconnected from {name}[/green]")
        else:
            console.print(f"[yellow]Server {name} was not connected[/yellow]")
    else:
        console.print("Disconnecting from all servers...")
        run_on_mcp_loop(registry.disconnect_all())
        console.print("[green]✓ Disconnected from all servers[/green]")


def mcp_discover() -> None:
    """
    Discover and list tools from all connected MCP servers.
    """
    from joshu.mcp.discovery import discover_mcp_tools

    # Auto-load servers from config files
    load_mcp_servers_from_config()

    console.print("Discovering tools from MCP servers...")

    try:
        tools = run_on_mcp_loop(discover_mcp_tools(connect_if_needed=True))

        if not tools:
            console.print("[yellow]No tools discovered.[/yellow]")
            console.print("Make sure MCP servers are configured and reachable.")
            return

        # Group by server
        by_server: dict = {}
        for tool in tools:
            server = tool.server_name or "unknown"
            if server not in by_server:
                by_server[server] = []
            by_server[server].append(tool)

        for server_name, server_tools in by_server.items():
            console.print(f"\n[bold cyan]{server_name}[/bold cyan]")
            for tool in server_tools:
                console.print(f"  [green]{tool.name}[/green]")
                if tool.description:
                    desc = (
                        tool.description[:60] + "..."
                        if len(tool.description) > 60
                        else tool.description
                    )
                    console.print(f"    {desc}")

        console.print(f"\n[dim]Total: {len(tools)} tools from {len(by_server)} servers[/dim]")

    except Exception as e:
        console.print(f"[red]Error discovering tools: {e}[/red]")
        raise typer.Exit(1)


def _expand_env_vars(env_dict: dict) -> dict:
    """
    Expand environment variable references in env dict values.

    Supports ${VAR_NAME} syntax. If the env var is not set,
    the original string is kept.

    Args:
        env_dict: Dictionary with potential ${VAR} references

    Returns:
        Dictionary with expanded values
    """
    import os
    import re

    expanded = {}
    for key, value in env_dict.items():
        if isinstance(value, str):
            # Match ${VAR_NAME} pattern
            def replace_var(match):
                var_name = match.group(1)
                return os.environ.get(var_name, match.group(0))

            expanded[key] = re.sub(r"\$\{([^}]+)\}", replace_var, value)
        else:
            expanded[key] = value

    return expanded


def load_mcp_servers_from_config() -> None:
    """
    Load MCP servers from configuration files into registry.

    Loads from both:
    1. Standard mcp.json file (Claude Desktop compatible format)
    2. config.yaml mcp_servers section
    """
    from joshu.mcp.registry import get_mcp_registry

    registry = get_mcp_registry()
    loaded_count = 0

    # First, try to load from mcp.json (standard format)
    loaded_count += _load_from_mcp_json(registry)

    # Then load from config.yaml (JoshuConfig format)
    config_manager = get_config_manager()
    mcp_servers = config_manager.get("mcp_servers", {}) or {}

    for name, server_config in mcp_servers.items():
        try:
            # Skip if already loaded from mcp.json
            if registry.get_server(name):
                continue
            registry.add_server_from_dict(name, server_config)
            logger.info(f"Loaded MCP server from config.yaml: {name}")
            loaded_count += 1
        except Exception as e:
            logger.error(f"Failed to load MCP server {name}: {e}")

    # Then the servers plugins declare (configured ones of the same name win)
    from joshu.core.plugins import plugin_mcp_servers

    for name, server_config in plugin_mcp_servers().items():
        try:
            if registry.get_server(name):
                continue
            registry.add_server_from_dict(name, server_config)
            logger.info(f"Loaded MCP server from a plugin: {name}")
            loaded_count += 1
        except Exception as e:
            logger.error(f"Failed to load plugin MCP server {name}: {e}")

    if loaded_count == 0:
        logger.debug("No MCP servers in configuration")


def _load_from_mcp_json(registry) -> int:
    """
    Load MCP servers from standard mcp.json file.

    Supports Claude Desktop compatible format:
    {
      "mcpServers": {
        "server-name": {
          "command": "...",
          "args": [...],
          "env": {...}
        }
      }
    }

    Returns:
        Number of servers loaded.
    """
    import json
    from pathlib import Path

    # Look for mcp.json in multiple locations
    search_paths = [
        Path(__file__).parent.parent.parent.parent.parent
        / "config"
        / "mcp.json",  # project/config/mcp.json
        Path.home() / ".joshu" / "mcp.json",  # ~/.joshu/mcp.json
        Path.cwd() / "mcp.json",  # current directory
    ]

    loaded_count = 0

    for mcp_json_path in search_paths:
        if mcp_json_path.exists():
            try:
                with open(mcp_json_path, "r") as f:
                    mcp_config = json.load(f)

                servers = mcp_config.get("mcpServers", {})

                for name, server_config in servers.items():
                    try:
                        # Convert from mcp.json format to our format
                        converted_config = {
                            "transport": "stdio",  # Default for mcp.json
                            "command": server_config.get("command"),
                            "args": server_config.get("args", []),
                            "env": _expand_env_vars(server_config.get("env", {})),
                            "enabled": True,
                        }

                        # Handle URL-based servers
                        if "url" in server_config:
                            converted_config["transport"] = "http"
                            converted_config["url"] = server_config["url"]

                        registry.add_server_from_dict(name, converted_config)
                        logger.info(f"Loaded MCP server from {mcp_json_path}: {name}")
                        loaded_count += 1
                    except Exception as e:
                        logger.error(f"Failed to load MCP server {name} from mcp.json: {e}")

                # Only load from first found mcp.json
                if loaded_count > 0:
                    console.print(
                        f"[dim]Loaded {loaded_count} MCP servers from {mcp_json_path}[/dim]"
                    )
                    break

            except json.JSONDecodeError as e:
                logger.error(f"Invalid JSON in {mcp_json_path}: {e}")
            except Exception as e:
                logger.error(f"Failed to read {mcp_json_path}: {e}")

    return loaded_count


def initialize_mcp_on_startup() -> None:
    """
    Initialize MCP integration on Joshu startup.

    Called during application initialization if mcp_enabled is True.
    """
    config_manager = get_config_manager()

    if not config_manager.get("mcp_enabled", True):
        logger.debug("MCP integration disabled")
        return

    # Load servers from config
    load_mcp_servers_from_config()

    # Auto-discover if configured
    if config_manager.get("mcp_discovery_on_startup", True):
        from joshu.mcp.discovery import register_mcp_tools_with_joshu

        try:
            count = run_on_mcp_loop(register_mcp_tools_with_joshu())
            if count > 0:
                logger.info(f"Registered {count} MCP tools on startup")
        except Exception as e:
            logger.warning(f"Failed to discover MCP tools on startup: {e}")
