"""
MCP Exception Definitions.

Custom exceptions for MCP-related errors.
"""

from __future__ import annotations


class MCPError(Exception):
    """Base exception for all MCP-related errors."""

    pass


class MCPConnectionError(MCPError):
    """
    Raised when connection to an MCP server fails.

    This can occur due to:
    - Server not running
    - Network issues
    - Invalid URL/command
    - Authentication failure
    """

    def __init__(self, server_name: str, message: str):
        self.server_name = server_name
        self.message = message
        super().__init__(f"Connection to MCP server '{server_name}' failed: {message}")


class MCPTransportError(MCPError):
    """
    Raised when transport-level communication fails.

    This includes:
    - JSON-RPC parsing errors
    - Protocol violations
    - Timeout errors
    - Stream errors
    """

    def __init__(self, server_name: str, message: str, transport_type: str = "unknown"):
        self.server_name = server_name
        self.message = message
        self.transport_type = transport_type
        super().__init__(
            f"Transport error ({transport_type}) for server '{server_name}': {message}"
        )


class MCPToolExecutionError(MCPError):
    """
    Raised when tool execution fails.

    This includes:
    - Tool not found
    - Invalid arguments
    - Runtime errors in tool
    - Permission denied
    """

    def __init__(self, tool_name: str, message: str, server_name: str = ""):
        self.tool_name = tool_name
        self.message = message
        self.server_name = server_name
        server_info = f" on server '{server_name}'" if server_name else ""
        super().__init__(f"Tool '{tool_name}'{server_info} execution failed: {message}")


class MCPConfigurationError(MCPError):
    """
    Raised when MCP configuration is invalid.

    This includes:
    - Missing required fields
    - Invalid transport type
    - Malformed server config
    - Conflicting settings
    """

    def __init__(self, message: str, config_key: str = ""):
        self.message = message
        self.config_key = config_key
        key_info = f" (key: {config_key})" if config_key else ""
        super().__init__(f"MCP configuration error{key_info}: {message}")


class MCPTimeoutError(MCPError):
    """
    Raised when an MCP operation times out.
    """

    def __init__(self, operation: str, timeout: int, server_name: str = ""):
        self.operation = operation
        self.timeout = timeout
        self.server_name = server_name
        server_info = f" for server '{server_name}'" if server_name else ""
        super().__init__(f"Operation '{operation}'{server_info} timed out after {timeout}s")


class MCPSecurityError(MCPError):
    """
    Raised when a security check fails.

    This includes:
    - Tool name sanitization failures
    - Schema validation failures
    - Unauthorized tool access
    """

    def __init__(self, message: str, tool_name: str = ""):
        self.message = message
        self.tool_name = tool_name
        tool_info = f" (tool: {tool_name})" if tool_name else ""
        super().__init__(f"MCP security error{tool_info}: {message}")
