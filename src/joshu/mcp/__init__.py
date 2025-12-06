"""
Model Context Protocol (MCP) Integration for Joshu.

This package provides MCP server integration, enabling Joshu to discover
and execute tools from external MCP-compliant servers.

Key components:
- schemas: Data models for MCP protocol
- transports: Communication layer (Stdio, HTTP)
- discovery: Tool discovery and registration
- registry: Server lifecycle management
- security: Sanitization and validation
"""

from joshu.mcp.discovery import DiscoveredMCPTool, discover_mcp_tools
from joshu.mcp.exceptions import (
    MCPConfigurationError,
    MCPConnectionError,
    MCPError,
    MCPToolExecutionError,
    MCPTransportError,
)
from joshu.mcp.registry import MCPServerRegistry, get_mcp_registry
from joshu.mcp.schemas import (
    MCPPromptDefinition,
    MCPResourceDefinition,
    MCPServerConfig,
    MCPToolDefinition,
    MCPToolResult,
)

__all__ = [
    # Schemas
    "MCPServerConfig",
    "MCPToolDefinition",
    "MCPResourceDefinition",
    "MCPPromptDefinition",
    "MCPToolResult",
    # Exceptions
    "MCPError",
    "MCPConnectionError",
    "MCPTransportError",
    "MCPToolExecutionError",
    "MCPConfigurationError",
    # Registry
    "MCPServerRegistry",
    "get_mcp_registry",
    # Discovery
    "discover_mcp_tools",
    "DiscoveredMCPTool",
]
