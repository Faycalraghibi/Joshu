"""
MCP Tool Discovery.

Discovers tools from connected MCP servers and registers them
with the Joshu tool registry.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List, Optional, Set

from joshu.mcp.exceptions import MCPToolExecutionError
from joshu.mcp.registry import MCPServerRegistry, get_mcp_registry
from joshu.mcp.schemas import MCPToolDefinition
from joshu.mcp.security import (
    is_tool_allowed,
    resolve_conflict,
    sanitize_description,
    sanitize_schema,
    sanitize_tool_name,
    validate_tool_definition,
)

logger = logging.getLogger(__name__)


class DiscoveredMCPTool:
    """
    Wrapper for an MCP tool that integrates with Joshu's tool system.

    Acts as a bridge between MCP tools and Joshu's ToolSpec format,
    handling async execution and result formatting.
    """

    def __init__(
        self,
        definition: MCPToolDefinition,
        registry: MCPServerRegistry,
    ):
        """
        Initialize discovered tool.

        Args:
            definition: MCP tool definition.
            registry: Server registry for transport access.
        """
        self.definition = definition
        self.registry = registry
        self._sanitized_name: Optional[str] = None

    @property
    def name(self) -> str:
        """Get the original tool name."""
        return self.definition.name

    @property
    def sanitized_name(self) -> str:
        """Get the sanitized tool name."""
        if self._sanitized_name is None:
            self._sanitized_name = sanitize_tool_name(
                self.definition.name,
                self.definition.server_name or "",
            )
        return self._sanitized_name

    @property
    def server_name(self) -> str:
        """Get the server name."""
        return self.definition.server_name or ""

    @property
    def description(self) -> str:
        """Get sanitized description."""
        return sanitize_description(self.definition.description)

    @property
    def parameters(self) -> Dict[str, Any]:
        """Get sanitized parameters schema."""
        return sanitize_schema(self.definition.parameters)

    async def execute(self, **arguments: Any) -> Dict[str, Any]:
        """
        Execute the MCP tool.

        Args:
            **arguments: Tool arguments.

        Returns:
            Execution result dictionary.
        """
        if not self.server_name:
            return {
                "success": False,
                "error": "Tool has no associated server",
            }

        transport = self.registry.get_transport(self.server_name)
        if not transport:
            return {
                "success": False,
                "error": f"Server '{self.server_name}' not connected",
            }

        try:
            result = await transport.call_tool(self.name, arguments)
            return result.to_dict()
        except MCPToolExecutionError as e:
            return {
                "success": False,
                "error": str(e),
                "tool_name": self.name,
                "server_name": self.server_name,
            }
        except Exception as e:
            logger.error(f"Unexpected error executing MCP tool {self.name}: {e}")
            return {
                "success": False,
                "error": f"Unexpected error: {str(e)}",
            }

    def __call__(self, **arguments: Any) -> Dict[str, Any]:
        """
        Synchronous wrapper for tool execution.

        Creates event loop if needed for sync context.
        """
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            # Already in async context, create task
            asyncio.ensure_future(self.execute(**arguments))
            # This is a compromise - we can't truly block in async
            # The caller should use execute() directly
            return {"success": False, "error": "Use execute() in async context"}
        else:
            # Create new event loop for sync call
            return asyncio.run(self.execute(**arguments))

    def to_tool_spec_dict(self) -> Dict[str, Any]:
        """
        Convert to a dictionary suitable for ToolSpec creation.

        Returns:
            Dictionary with name, description, parameters, function.
        """
        return {
            "name": self.sanitized_name,
            "description": self.description,
            "parameters": self.parameters,
            "function": self,  # Callable
            "enabled": True,
            "requires_approval": False,
            "source": "mcp",
            "server_name": self.server_name,
        }


async def discover_mcp_tools(
    registry: Optional[MCPServerRegistry] = None,
    connect_if_needed: bool = True,
) -> List[DiscoveredMCPTool]:
    """
    Discover tools from all configured MCP servers.

    Args:
        registry: MCP server registry (uses global if None).
        connect_if_needed: Connect to servers if not already connected.

    Returns:
        List of discovered tools.
    """
    if registry is None:
        registry = get_mcp_registry()

    tools: List[DiscoveredMCPTool] = []

    for server_config in registry.list_servers():
        if not server_config.enabled:
            logger.debug(f"Skipping disabled server: {server_config.name}")
            continue

        # Connect if needed
        if connect_if_needed and not registry.is_connected(server_config.name):
            try:
                await registry.connect_server(server_config.name)
            except Exception as e:
                logger.error(f"Failed to connect to {server_config.name}: {e}")
                continue

        transport = registry.get_transport(server_config.name)
        if not transport:
            logger.warning(f"No transport for {server_config.name}")
            continue

        # Discover tools from this server
        try:
            server_tools = await transport.list_tools()

            for tool_def in server_tools:
                # Apply include/exclude filters
                if not is_tool_allowed(
                    tool_def.name,
                    server_config.include_tools,
                    server_config.exclude_tools,
                ):
                    logger.debug(f"Tool '{tool_def.name}' filtered out by config")
                    continue

                # Validate
                if not validate_tool_definition(tool_def):
                    logger.warning(f"Invalid tool definition: {tool_def.name}")
                    continue

                # Create wrapper
                wrapper = DiscoveredMCPTool(tool_def, registry)
                tools.append(wrapper)

            logger.info(f"Discovered {len(server_tools)} tools from {server_config.name}")

        except Exception as e:
            logger.error(f"Failed to discover tools from {server_config.name}: {e}")

    return tools


async def register_mcp_tools_with_joshu(
    tools: Optional[List[DiscoveredMCPTool]] = None,
    registry: Optional[MCPServerRegistry] = None,
) -> int:
    """
    Register discovered MCP tools with Joshu's ToolRegistry.

    Args:
        tools: Pre-discovered tools (discovers if None).
        registry: MCP registry (uses global if None).

    Returns:
        Number of tools registered.
    """
    from joshu.core.tool_registry import ToolRegistry, ToolSpec

    if tools is None:
        tools = await discover_mcp_tools(registry)

    tool_registry = ToolRegistry()
    existing_names: Set[str] = set(tool_registry.list_tools())
    registered_count = 0

    for mcp_tool in tools:
        try:
            # Resolve naming conflicts
            final_name = resolve_conflict(
                mcp_tool.definition,
                existing_names,
                strategy="namespace",
            )

            # Create ToolSpec
            spec = ToolSpec(
                name=final_name,
                description=mcp_tool.description,
                parameters=mcp_tool.parameters,
                function=mcp_tool,
                enabled=True,
                requires_approval=False,
            )

            if tool_registry.register(spec):
                existing_names.add(final_name)
                registered_count += 1
                logger.debug(f"Registered MCP tool: {final_name}")

        except Exception as e:
            logger.error(f"Failed to register tool {mcp_tool.name}: {e}")

    logger.info(f"Registered {registered_count} MCP tools")
    return registered_count


def discover_tools_sync(
    registry: Optional[MCPServerRegistry] = None,
) -> List[DiscoveredMCPTool]:
    """
    Synchronous wrapper for tool discovery.

    Args:
        registry: MCP server registry.

    Returns:
        List of discovered tools.
    """
    return asyncio.run(discover_mcp_tools(registry))
