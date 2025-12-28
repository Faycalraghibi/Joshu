"""
MCP Server Management Command Handlers.

Provides command handlers for managing MCP server configurations:
- joshu mcp add - Add a new MCP server
- joshu mcp list - List configured servers
- joshu mcp remove - Remove a server
- joshu mcp status - Show server connection status
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Dict, List, Optional

from joshu.commands.types import (
    CommandActionReturn,
    ErrorActionReturn,
    MessageActionReturn,
)
from joshu.mcp.registry import get_mcp_registry
from joshu.mcp.schemas import MCPServerConfig, TransportType

logger = logging.getLogger(__name__)


@dataclass
class MCPAddConfig:
    """Configuration for adding an MCP server."""

    name: str
    command: Optional[str] = None  # For stdio transport
    url: Optional[str] = None  # For http/sse transport
    args: Optional[List[str]] = None
    env: Optional[Dict[str, str]] = None
    timeout: int = 30


def mcp_add(config: MCPAddConfig) -> CommandActionReturn:
    """
    Add a new MCP server configuration.

    Args:
        config: Server configuration

    Returns:
        CommandActionReturn with result
    """
    try:
        if config.command:
            transport = TransportType.STDIO
        elif config.url:
            if "sse" in config.url.lower() or config.url.endswith("/events"):
                transport = TransportType.SSE
            else:
                transport = TransportType.HTTP
        else:
            return ErrorActionReturn(
                error_message="Must specify either --command (stdio) or --url (http/sse)",
                error_code="INVALID_CONFIG",
                recoverable=True,
            )

        server_config = MCPServerConfig(
            name=config.name,
            transport=transport,
            command=config.command,
            args=config.args or [],
            url=config.url,
            env=config.env or {},
            timeout=config.timeout,
            enabled=True,
        )

        server_config.validate()

        registry = get_mcp_registry()
        registry.add_server(server_config)

        logger.info(f"Added MCP server: {config.name}")

        return MessageActionReturn(
            message=f"✓ Added MCP server '{config.name}' ({transport.value} transport)",
            message_type="success",
            metadata={
                "name": config.name,
                "transport": transport.value,
                "command": config.command,
                "url": config.url,
            },
        )

    except Exception as e:
        logger.error(f"Failed to add MCP server: {e}")
        return ErrorActionReturn(
            error_message=f"Failed to add server: {str(e)}",
            error_code="ADD_FAILED",
            recoverable=True,
        )


def mcp_list() -> CommandActionReturn:
    """
    List all configured MCP servers.

    Returns:
        CommandActionReturn with server list
    """
    try:
        registry = get_mcp_registry()
        servers = registry.list_servers()

        if not servers:
            return MessageActionReturn(
                message="No MCP servers configured",
                message_type="info",
            )

        lines = ["**Configured MCP Servers:**", ""]
        for server in servers:
            status_icon = "🟢" if registry.is_connected(server.name) else "⚪"
            enabled = "enabled" if server.enabled else "disabled"
            transport = server.transport.value

            lines.append(f"  {status_icon} **{server.name}** ({transport}, {enabled})")

            if server.command:
                lines.append(f"      Command: `{server.command}`")
            if server.url:
                lines.append(f"      URL: {server.url}")

        return MessageActionReturn(
            message="\n".join(lines),
            message_type="info",
            metadata={"servers": [s.to_dict() for s in servers]},
        )

    except Exception as e:
        logger.error(f"Failed to list MCP servers: {e}")
        return ErrorActionReturn(
            error_message=f"Failed to list servers: {str(e)}",
            error_code="LIST_FAILED",
            recoverable=True,
        )


def mcp_remove(name: str) -> CommandActionReturn:
    """
    Remove an MCP server configuration.

    Args:
        name: Server name to remove

    Returns:
        CommandActionReturn with result
    """
    try:
        registry = get_mcp_registry()

        if not registry.get_server(name):
            return ErrorActionReturn(
                error_message=f"Server not found: {name}",
                error_code="NOT_FOUND",
                recoverable=True,
            )

        if registry.is_connected(name):
            try:
                asyncio.get_event_loop().run_until_complete(registry.disconnect_server(name))
            except RuntimeError:
                # No event loop, create a new one
                asyncio.run(registry.disconnect_server(name))

        registry.remove_server(name)

        logger.info(f"Removed MCP server: {name}")

        return MessageActionReturn(
            message=f"✓ Removed MCP server '{name}'",
            message_type="success",
        )

    except Exception as e:
        logger.error(f"Failed to remove MCP server: {e}")
        return ErrorActionReturn(
            error_message=f"Failed to remove server: {str(e)}",
            error_code="REMOVE_FAILED",
            recoverable=True,
        )


def mcp_status() -> CommandActionReturn:
    """
    Show status of all MCP servers.

    Returns:
        CommandActionReturn with status information
    """
    try:
        registry = get_mcp_registry()
        status = registry.get_status()

        if not status:
            return MessageActionReturn(
                message="No MCP servers configured",
                message_type="info",
            )

        lines = ["**MCP Server Status:**", ""]

        for name, info in status.items():
            connected = info.get("connected", False)
            enabled = info.get("enabled", False)
            transport = info.get("transport", "unknown")

            if connected:
                status_text = "🟢 Connected"
            elif enabled:
                status_text = "🟡 Disconnected"
            else:
                status_text = "⚫ Disabled"

            lines.append(f"  **{name}** - {status_text}")
            lines.append(f"      Transport: {transport}")

            if info.get("tool_count"):
                lines.append(f"      Tools: {info['tool_count']}")

            if info.get("error"):
                lines.append(f"      Error: {info['error']}")

        return MessageActionReturn(
            message="\n".join(lines),
            message_type="info",
            metadata={"status": status},
        )

    except Exception as e:
        logger.error(f"Failed to get MCP status: {e}")
        return ErrorActionReturn(
            error_message=f"Failed to get status: {str(e)}",
            error_code="STATUS_FAILED",
            recoverable=True,
        )


def mcp_connect(name: str) -> CommandActionReturn:
    """
    Connect to an MCP server.

    Args:
        name: Server name to connect

    Returns:
        CommandActionReturn with result
    """
    try:
        registry = get_mcp_registry()

        if not registry.get_server(name):
            return ErrorActionReturn(
                error_message=f"Server not found: {name}",
                error_code="NOT_FOUND",
                recoverable=True,
            )

        if registry.is_connected(name):
            return MessageActionReturn(
                message=f"Already connected to '{name}'",
                message_type="info",
            )

        # Connect (this is async, so we need to run it)
        try:
            success = asyncio.get_event_loop().run_until_complete(registry.connect_server(name))
        except RuntimeError:
            # No event loop, create a new one
            success = asyncio.run(registry.connect_server(name))

        if success:
            return MessageActionReturn(
                message=f"✓ Connected to MCP server '{name}'",
                message_type="success",
            )
        else:
            return ErrorActionReturn(
                error_message=f"Failed to connect to '{name}'",
                error_code="CONNECT_FAILED",
                recoverable=True,
            )

    except Exception as e:
        logger.error(f"Failed to connect to MCP server: {e}")
        return ErrorActionReturn(
            error_message=f"Connection failed: {str(e)}",
            error_code="CONNECT_FAILED",
            recoverable=True,
        )


def mcp_disconnect(name: str) -> CommandActionReturn:
    """
    Disconnect from an MCP server.

    Args:
        name: Server name to disconnect

    Returns:
        CommandActionReturn with result
    """
    try:
        registry = get_mcp_registry()

        if not registry.get_server(name):
            return ErrorActionReturn(
                error_message=f"Server not found: {name}",
                error_code="NOT_FOUND",
                recoverable=True,
            )

        if not registry.is_connected(name):
            return MessageActionReturn(
                message=f"Not connected to '{name}'",
                message_type="info",
            )

        try:
            asyncio.get_event_loop().run_until_complete(registry.disconnect_server(name))
        except RuntimeError:
            # No event loop, create a new one
            asyncio.run(registry.disconnect_server(name))

        return MessageActionReturn(
            message=f"✓ Disconnected from MCP server '{name}'",
            message_type="success",
        )

    except Exception as e:
        logger.error(f"Failed to disconnect from MCP server: {e}")
        return ErrorActionReturn(
            error_message=f"Disconnect failed: {str(e)}",
            error_code="DISCONNECT_FAILED",
            recoverable=True,
        )
