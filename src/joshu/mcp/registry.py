"""
MCP Server Registry.

Manages MCP server configurations and lifecycle.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List, Optional

from joshu.mcp.exceptions import MCPConfigurationError, MCPConnectionError
from joshu.mcp.schemas import MCPServerConfig, TransportType
from joshu.mcp.transports.base import MCPTransport
from joshu.mcp.transports.http import HTTPTransport
from joshu.mcp.transports.stdio import StdioTransport

logger = logging.getLogger(__name__)


class MCPServerRegistry:
    """
    Registry for managing MCP server configurations and connections.

    Handles:
    - Server configuration storage
    - Transport creation and management
    - Connection lifecycle (connect/disconnect)
    - Server status tracking
    """

    _instance: Optional["MCPServerRegistry"] = None

    def __new__(cls) -> "MCPServerRegistry":
        """Ensure singleton instance."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        """Initialize the registry."""
        if self._initialized:
            return

        self._servers: Dict[str, MCPServerConfig] = {}
        self._transports: Dict[str, MCPTransport] = {}
        self._initialized = True
        logger.info("MCP Server Registry initialized")

    def add_server(self, config: MCPServerConfig) -> bool:
        """
        Add a new server configuration.

        Args:
            config: Server configuration.

        Returns:
            True if successful.

        Raises:
            MCPConfigurationError: If config is invalid.
        """
        if not config.validate():
            raise MCPConfigurationError("Invalid server configuration", config.name)

        if config.name in self._servers:
            logger.warning(f"Server '{config.name}' already exists, updating")

        self._servers[config.name] = config
        logger.info(f"Added MCP server: {config.name}")
        return True

    def add_server_from_dict(self, name: str, config_dict: Dict[str, Any]) -> bool:
        """
        Add server configuration from dictionary (e.g., from config file).

        Args:
            name: Server name.
            config_dict: Configuration dictionary.

        Returns:
            True if successful.
        """
        config = MCPServerConfig.from_dict(name, config_dict)
        return self.add_server(config)

    def remove_server(self, name: str) -> bool:
        """
        Remove a server configuration and disconnect if connected.

        Args:
            name: Server name to remove.

        Returns:
            True if server was removed, False if not found.
        """
        if name not in self._servers:
            logger.warning(f"Server '{name}' not found")
            return False

        # Disconnect if connected
        if name in self._transports:
            asyncio.create_task(self._disconnect_server(name))

        del self._servers[name]
        logger.info(f"Removed MCP server: {name}")
        return True

    def get_server(self, name: str) -> Optional[MCPServerConfig]:
        """
        Get server configuration by name.

        Args:
            name: Server name.

        Returns:
            Server config or None if not found.
        """
        return self._servers.get(name)

    def list_servers(self) -> List[MCPServerConfig]:
        """
        Get list of all configured servers.

        Returns:
            List of server configurations.
        """
        return list(self._servers.values())

    def get_server_names(self) -> List[str]:
        """
        Get list of all server names.

        Returns:
            List of server names.
        """
        return list(self._servers.keys())

    def is_connected(self, name: str) -> bool:
        """
        Check if a server is connected.

        Args:
            name: Server name.

        Returns:
            True if connected.
        """
        transport = self._transports.get(name)
        return transport is not None and transport.is_connected

    async def connect_server(self, name: str) -> bool:
        """
        Connect to a configured server.

        Args:
            name: Server name to connect.

        Returns:
            True if connection successful.

        Raises:
            MCPConnectionError: If connection fails.
        """
        config = self._servers.get(name)
        if not config:
            raise MCPConfigurationError(f"Server '{name}' not configured")

        if not config.enabled:
            logger.info(f"Server '{name}' is disabled, skipping connection")
            return False

        # Create transport based on type
        transport = self._create_transport(config)

        try:
            await transport.connect()
            self._transports[name] = transport
            logger.info(f"Connected to MCP server: {name}")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to {name}: {e}")
            raise MCPConnectionError(name, str(e))

    async def disconnect_server(self, name: str) -> bool:
        """
        Disconnect from a server.

        Args:
            name: Server name to disconnect.

        Returns:
            True if disconnected successfully.
        """
        return await self._disconnect_server(name)

    async def _disconnect_server(self, name: str) -> bool:
        """Internal disconnect implementation."""
        transport = self._transports.pop(name, None)
        if transport:
            try:
                await transport.disconnect()
                logger.info(f"Disconnected from MCP server: {name}")
                return True
            except Exception as e:
                logger.error(f"Error disconnecting from {name}: {e}")
        return False

    async def connect_all(self) -> Dict[str, bool]:
        """
        Connect to all configured and enabled servers.

        Returns:
            Dict mapping server names to connection success.
        """
        results = {}
        for name, config in self._servers.items():
            if config.enabled:
                try:
                    results[name] = await self.connect_server(name)
                except Exception as e:
                    logger.error(f"Failed to connect to {name}: {e}")
                    results[name] = False
            else:
                results[name] = False
        return results

    async def disconnect_all(self) -> None:
        """Disconnect from all servers."""
        for name in list(self._transports.keys()):
            await self._disconnect_server(name)

    def get_transport(self, name: str) -> Optional[MCPTransport]:
        """
        Get transport for a connected server.

        Args:
            name: Server name.

        Returns:
            Transport instance or None if not connected.
        """
        return self._transports.get(name)

    def get_connected_transports(self) -> Dict[str, MCPTransport]:
        """
        Get all connected transports.

        Returns:
            Dict mapping server names to transports.
        """
        return {
            name: transport
            for name, transport in self._transports.items()
            if transport.is_connected
        }

    def _create_transport(self, config: MCPServerConfig) -> MCPTransport:
        """
        Create appropriate transport for server config.

        Args:
            config: Server configuration.

        Returns:
            Transport instance.

        Raises:
            MCPConfigurationError: If transport type unknown.
        """
        if config.transport == TransportType.STDIO:
            return StdioTransport(config)
        elif config.transport in (TransportType.HTTP, TransportType.SSE):
            return HTTPTransport(config)
        else:
            raise MCPConfigurationError(f"Unknown transport type: {config.transport}", config.name)

    def get_status(self) -> Dict[str, Dict[str, Any]]:
        """
        Get status of all servers.

        Returns:
            Dict with server status information.
        """
        status = {}
        for name, config in self._servers.items():
            transport = self._transports.get(name)
            status[name] = {
                "enabled": config.enabled,
                "transport": config.transport.value,
                "connected": transport is not None and transport.is_connected,
                "url": config.url,
                "command": config.command,
            }
        return status

    def clear(self) -> None:
        """Clear all servers (for testing)."""
        asyncio.create_task(self.disconnect_all())
        self._servers.clear()
        self._transports.clear()
        logger.info("Cleared MCP server registry")


# Global registry instance
_registry: Optional[MCPServerRegistry] = None


def get_mcp_registry() -> MCPServerRegistry:
    """
    Get the global MCP server registry instance.

    Returns:
        MCPServerRegistry singleton instance.
    """
    global _registry
    if _registry is None:
        _registry = MCPServerRegistry()
    return _registry
