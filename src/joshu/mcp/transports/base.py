"""
MCP Transport Base Class.

Abstract base class for MCP transport implementations.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from joshu.mcp.schemas import (
    MCPPromptDefinition,
    MCPResourceDefinition,
    MCPServerConfig,
    MCPToolDefinition,
    MCPToolResult,
)

logger = logging.getLogger(__name__)


class MCPTransport(ABC):
    """
    Abstract base class for MCP transports.

    Transports handle the low-level communication with MCP servers,
    including connection management and JSON-RPC message handling.
    """

    def __init__(self, config: MCPServerConfig):
        """
        Initialize the transport.

        Args:
            config: Server configuration
        """
        self.config = config
        self._connected = False
        self._server_info: Optional[Dict[str, Any]] = None

    @property
    def is_connected(self) -> bool:
        """Return True if connected to the server."""
        return self._connected

    @property
    def server_name(self) -> str:
        """Return the server name."""
        return self.config.name

    @abstractmethod
    async def connect(self) -> bool:
        """
        Establish connection to the MCP server.

        Returns:
            True if connection successful, False otherwise.

        Raises:
            MCPConnectionError: If connection fails.
        """
        pass

    @abstractmethod
    async def disconnect(self) -> None:
        """
        Close connection to the MCP server.

        This should clean up all resources (processes, connections).
        """
        pass

    @abstractmethod
    async def list_tools(self) -> List[MCPToolDefinition]:
        """
        Get list of available tools from the server.

        Returns:
            List of tool definitions.

        Raises:
            MCPTransportError: If request fails.
        """
        pass

    @abstractmethod
    async def call_tool(
        self,
        name: str,
        arguments: Dict[str, Any],
    ) -> MCPToolResult:
        """
        Execute a tool on the MCP server.

        Args:
            name: Name of the tool to execute.
            arguments: Tool arguments.

        Returns:
            Tool execution result.

        Raises:
            MCPToolExecutionError: If tool execution fails.
        """
        pass

    @abstractmethod
    async def list_resources(self) -> List[MCPResourceDefinition]:
        """
        Get list of available resources from the server.

        Returns:
            List of resource definitions.

        Raises:
            MCPTransportError: If request fails.
        """
        pass

    @abstractmethod
    async def read_resource(self, uri: str) -> Any:
        """
        Read a resource from the server.

        Args:
            uri: Resource URI to read.

        Returns:
            Resource content.

        Raises:
            MCPTransportError: If request fails.
        """
        pass

    async def list_prompts(self) -> List[MCPPromptDefinition]:
        """
        Get list of available prompts from the server.

        Returns:
            List of prompt definitions.

        Raises:
            MCPTransportError: If request fails.
        """
        # Default implementation returns empty list
        # Subclasses can override if they support prompts
        return []

    async def get_prompt(
        self,
        name: str,
        arguments: Optional[Dict[str, Any]] = None,
    ) -> Optional[str]:
        """
        Get a prompt from the server.

        Args:
            name: Prompt name.
            arguments: Prompt arguments.

        Returns:
            Prompt content or None if not found.
        """
        send = getattr(self, "_send_request", None)
        if send is None:
            return None
        result = await send("prompts/get", {"name": name, "arguments": arguments or {}})
        parts = []
        for message in (result or {}).get("messages", []):
            content = message.get("content") or {}
            if isinstance(content, dict) and content.get("type") == "text":
                parts.append(str(content.get("text", "")))
            elif isinstance(content, dict) and content.get("type") == "resource":
                resource = content.get("resource") or {}
                parts.append(str(resource.get("text", "")))
            elif isinstance(content, str):
                parts.append(content)
        return "\n\n".join(p for p in parts if p) or None

    async def ping(self) -> bool:
        """
        Check if the server is responsive.

        Returns:
            True if server responds, False otherwise.
        """
        try:
            # Try to list tools as a connectivity check
            await self.list_tools()
            return True
        except Exception:
            return False

    def get_server_info(self) -> Optional[Dict[str, Any]]:
        """
        Get server information from initialization.

        Returns:
            Server info dict or None if not connected.
        """
        return self._server_info

    async def __aenter__(self) -> "MCPTransport":
        """Async context manager entry."""
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit."""
        await self.disconnect()
