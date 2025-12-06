"""
MCP Schema Definitions.

This module defines Pydantic models for MCP protocol entities including
server configurations, tool definitions, resources, prompts, and results.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class TransportType(str, Enum):
    """Supported MCP transport types."""

    STDIO = "stdio"
    HTTP = "http"
    SSE = "sse"


@dataclass
class MCPServerConfig:
    """
    Configuration for an MCP server connection.

    Attributes:
        name: Unique identifier for this server
        transport: Transport type (stdio, http, sse)
        command: Command to run for stdio transport
        args: Command arguments for stdio transport
        url: URL for HTTP/SSE transport
        env: Environment variables for subprocess
        include_tools: Whitelist of tool names to include
        exclude_tools: Blacklist of tool names to exclude
        enabled: Whether this server is enabled
        timeout: Connection timeout in seconds
    """

    name: str
    transport: TransportType = TransportType.STDIO
    command: Optional[str] = None
    args: List[str] = field(default_factory=list)
    url: Optional[str] = None
    env: Dict[str, str] = field(default_factory=dict)
    include_tools: List[str] = field(default_factory=list)
    exclude_tools: List[str] = field(default_factory=list)
    enabled: bool = True
    timeout: int = 30

    def validate(self) -> bool:
        """Validate the server configuration."""
        if self.transport == TransportType.STDIO:
            if not self.command:
                return False
        elif self.transport in (TransportType.HTTP, TransportType.SSE):
            if not self.url:
                return False
        return True

    @classmethod
    def from_dict(cls, name: str, data: Dict[str, Any]) -> "MCPServerConfig":
        """Create from dictionary configuration."""
        transport_str = data.get("transport", "stdio")
        try:
            transport = TransportType(transport_str)
        except ValueError:
            transport = TransportType.STDIO

        return cls(
            name=name,
            transport=transport,
            command=data.get("command"),
            args=data.get("args", []),
            url=data.get("url"),
            env=data.get("env", {}),
            include_tools=data.get("include_tools", []),
            exclude_tools=data.get("exclude_tools", []),
            enabled=data.get("enabled", True),
            timeout=data.get("timeout", 30),
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        result: Dict[str, Any] = {
            "transport": self.transport.value,
            "enabled": self.enabled,
            "timeout": self.timeout,
        }

        if self.command:
            result["command"] = self.command
        if self.args:
            result["args"] = self.args
        if self.url:
            result["url"] = self.url
        if self.env:
            result["env"] = self.env
        if self.include_tools:
            result["include_tools"] = self.include_tools
        if self.exclude_tools:
            result["exclude_tools"] = self.exclude_tools

        return result


@dataclass
class MCPToolParameter:
    """Definition of a tool parameter."""

    name: str
    type: str
    description: str = ""
    required: bool = False
    default: Optional[Any] = None
    enum: Optional[List[Any]] = None


@dataclass
class MCPToolDefinition:
    """
    Definition of an MCP tool.

    Follows the MCP tool schema format compatible with OpenAI function calling.
    """

    name: str
    description: str
    parameters: Dict[str, Any] = field(default_factory=lambda: {"type": "object", "properties": {}})
    server_name: Optional[str] = None

    def to_openai_format(self) -> Dict[str, Any]:
        """Convert to OpenAI function calling format."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }

    @classmethod
    def from_mcp_response(cls, data: Dict[str, Any], server_name: str) -> "MCPToolDefinition":
        """Create from MCP list_tools response item."""
        return cls(
            name=data.get("name", ""),
            description=data.get("description", ""),
            parameters=data.get("inputSchema", {"type": "object", "properties": {}}),
            server_name=server_name,
        )


@dataclass
class MCPResourceDefinition:
    """
    Definition of an MCP resource.

    Resources provide data/information to LLMs (similar to GET endpoints).
    """

    uri: str
    name: str
    description: str = ""
    mime_type: Optional[str] = None
    server_name: Optional[str] = None

    @classmethod
    def from_mcp_response(cls, data: Dict[str, Any], server_name: str) -> "MCPResourceDefinition":
        """Create from MCP list_resources response item."""
        return cls(
            uri=data.get("uri", ""),
            name=data.get("name", ""),
            description=data.get("description", ""),
            mime_type=data.get("mimeType"),
            server_name=server_name,
        )


@dataclass
class MCPPromptDefinition:
    """
    Definition of an MCP prompt template.

    Prompts define reusable interaction patterns.
    """

    name: str
    description: str = ""
    arguments: List[Dict[str, Any]] = field(default_factory=list)
    server_name: Optional[str] = None

    @classmethod
    def from_mcp_response(cls, data: Dict[str, Any], server_name: str) -> "MCPPromptDefinition":
        """Create from MCP list_prompts response item."""
        return cls(
            name=data.get("name", ""),
            description=data.get("description", ""),
            arguments=data.get("arguments", []),
            server_name=server_name,
        )


@dataclass
class MCPToolResult:
    """
    Result from executing an MCP tool.

    Wraps the tool execution response with metadata.
    """

    success: bool
    content: Any = None
    error: Optional[str] = None
    tool_name: str = ""
    server_name: str = ""
    is_error: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for LLM consumption."""
        if self.success:
            return {
                "success": True,
                "result": self.content,
                "tool_name": self.tool_name,
                "server_name": self.server_name,
            }
        else:
            return {
                "success": False,
                "error": self.error or "Unknown error",
                "tool_name": self.tool_name,
                "server_name": self.server_name,
            }


@dataclass
class MCPContentBlock:
    """
    Content block from MCP tool result.

    MCP tools can return rich, multi-part content.
    """

    type: str  # "text", "image", "resource"
    text: Optional[str] = None
    data: Optional[str] = None  # Base64 for images
    mime_type: Optional[str] = None
    uri: Optional[str] = None

    @classmethod
    def from_mcp_response(cls, data: Dict[str, Any]) -> "MCPContentBlock":
        """Create from MCP content block response."""
        return cls(
            type=data.get("type", "text"),
            text=data.get("text"),
            data=data.get("data"),
            mime_type=data.get("mimeType"),
            uri=data.get("uri"),
        )

    def get_text_content(self) -> str:
        """Extract text content from the block."""
        if self.type == "text" and self.text:
            return self.text
        elif self.type == "resource" and self.uri:
            return f"[Resource: {self.uri}]"
        elif self.type == "image":
            return "[Image content]"
        return ""
