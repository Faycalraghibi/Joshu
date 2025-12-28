"""
MCP Security Utilities.

Provides security functions for sanitization, validation,
and conflict resolution when integrating MCP tools.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Set

from joshu.mcp.exceptions import MCPSecurityError
from joshu.mcp.schemas import MCPToolDefinition

logger = logging.getLogger(__name__)

RESERVED_TOOL_NAMES: Set[str] = {
    "web_search",
    "web_fetch",
    # Add other built-in tools here
}

MAX_TOOL_NAME_LENGTH = 64
MAX_DESCRIPTION_LENGTH = 1024
MAX_PARAMETER_DEPTH = 5


def sanitize_tool_name(name: str, server_name: str = "") -> str:
    """
    Sanitize a tool name to ensure it's safe and valid.

    Rules:
    - Only alphanumeric characters and underscores allowed
    - Must start with a letter
    - Maximum length enforced
    - Server prefix added for namespacing

    Args:
        name: Original tool name from MCP server.
        server_name: Server name for namespace prefix.

    Returns:
        Sanitized tool name.

    Raises:
        MCPSecurityError: If name cannot be sanitized.
    """
    if not name:
        raise MCPSecurityError("Tool name cannot be empty")

    sanitized = re.sub(r"[^a-zA-Z0-9_]", "_", name)

    if sanitized and not sanitized[0].isalpha():
        sanitized = "tool_" + sanitized

    if len(sanitized) > MAX_TOOL_NAME_LENGTH:
        sanitized = sanitized[:MAX_TOOL_NAME_LENGTH]

    # Add server namespace if provided and not already prefixed
    if server_name and not sanitized.startswith(f"{server_name}_"):
        prefix = re.sub(r"[^a-zA-Z0-9_]", "_", server_name)
        sanitized = f"{prefix}_{sanitized}"

        # Re-check length after prefixing
        if len(sanitized) > MAX_TOOL_NAME_LENGTH:
            sanitized = sanitized[:MAX_TOOL_NAME_LENGTH]

    if not sanitized:
        raise MCPSecurityError("Could not sanitize tool name", name)

    return sanitized


def sanitize_description(description: str) -> str:
    """
    Sanitize a tool description.

    Args:
        description: Original description.

    Returns:
        Sanitized description.
    """
    if not description:
        return ""

    sanitized = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]", "", description)

    if len(sanitized) > MAX_DESCRIPTION_LENGTH:
        sanitized = sanitized[: MAX_DESCRIPTION_LENGTH - 3] + "..."

    return sanitized.strip()


def sanitize_schema(schema: Dict[str, Any], depth: int = 0) -> Dict[str, Any]:
    """
    Sanitize a JSON schema for tool parameters.

    Args:
        schema: Original schema.
        depth: Current recursion depth.

    Returns:
        Sanitized schema.

    Raises:
        MCPSecurityError: If schema is invalid or too deeply nested.
    """
    if depth > MAX_PARAMETER_DEPTH:
        raise MCPSecurityError(f"Schema exceeds maximum depth of {MAX_PARAMETER_DEPTH}")

    if not isinstance(schema, dict):
        return {"type": "object", "properties": {}}

    sanitized: Dict[str, Any] = {}

    allowed_keys = {"type", "properties", "required", "items", "enum", "description", "default"}

    for key in allowed_keys:
        if key in schema:
            if key == "properties" and isinstance(schema[key], dict):
                sanitized[key] = {
                    k: sanitize_schema(v, depth + 1)
                    for k, v in schema[key].items()
                    if isinstance(k, str) and len(k) <= 64
                }
            elif key == "items" and isinstance(schema[key], dict):
                sanitized[key] = sanitize_schema(schema[key], depth + 1)
            elif key == "required" and isinstance(schema[key], list):
                sanitized[key] = [r for r in schema[key] if isinstance(r, str)]
            elif key == "enum" and isinstance(schema[key], list):
                sanitized[key] = schema[key][:50]
            elif key == "description":
                sanitized[key] = sanitize_description(str(schema[key]))
            else:
                sanitized[key] = schema[key]

    if sanitized.get("type") not in (
        "object",
        "string",
        "integer",
        "number",
        "boolean",
        "array",
        None,
    ):
        sanitized["type"] = "string"

    return sanitized


def is_tool_allowed(
    tool_name: str,
    include_tools: List[str],
    exclude_tools: List[str],
) -> bool:
    """
    Check if a tool should be included based on whitelist/blacklist.

    Args:
        tool_name: Name of the tool to check.
        include_tools: Whitelist (if non-empty, only these are allowed).
        exclude_tools: Blacklist (these are never allowed).

    Returns:
        True if tool is allowed, False otherwise.
    """
    if exclude_tools and tool_name in exclude_tools:
        return False

    # If whitelist is specified, tool must be in it
    if include_tools:
        return tool_name in include_tools

    return True


def resolve_conflict(
    new_tool: MCPToolDefinition,
    existing_names: Set[str],
    strategy: str = "namespace",
) -> str:
    """
    Resolve naming conflict when a tool name already exists.

    Args:
        new_tool: New tool definition with conflicting name.
        existing_names: Set of existing tool names.
        strategy: Resolution strategy ("namespace", "skip", "replace").

    Returns:
        Resolved tool name.

    Raises:
        MCPSecurityError: If conflict cannot be resolved or tool is reserved.
    """
    original_name = new_tool.name

    if original_name in RESERVED_TOOL_NAMES:
        if strategy == "replace":
            raise MCPSecurityError(f"Cannot replace reserved tool: {original_name}", original_name)
        # Must namespace reserved names
        strategy = "namespace"

    if original_name not in existing_names:
        return original_name

    if strategy == "skip":
        raise MCPSecurityError(f"Tool name conflict: {original_name} already exists", original_name)

    if strategy == "replace":
        logger.warning(f"Replacing existing tool: {original_name}")
        return original_name

    # Default: namespace with server name
    if new_tool.server_name:
        namespaced = f"{new_tool.server_name}_{original_name}"
        namespaced = sanitize_tool_name(namespaced)

        # Still conflicts? Add counter
        counter = 1
        candidate = namespaced
        while candidate in existing_names:
            candidate = f"{namespaced}_{counter}"
            counter += 1
            if counter > 100:
                raise MCPSecurityError(
                    f"Could not resolve conflict for: {original_name}", original_name
                )

        logger.info(f"Renamed tool {original_name} to {candidate} to avoid conflict")
        return candidate

    raise MCPSecurityError(
        f"Cannot resolve conflict for tool without server name: {original_name}", original_name
    )


def validate_tool_definition(tool: MCPToolDefinition) -> bool:
    """
    Validate an MCP tool definition.

    Args:
        tool: Tool definition to validate.

    Returns:
        True if valid, False otherwise.
    """
    if not tool.name:
        logger.warning("Tool missing name")
        return False

    if not tool.description:
        logger.warning(f"Tool {tool.name} missing description")
        # Description is recommended but not required

    if not re.match(r"^[a-zA-Z][a-zA-Z0-9_]*$", tool.name):
        logger.warning(f"Tool {tool.name} has invalid name format")
        return False

    if tool.parameters:
        if not isinstance(tool.parameters, dict):
            logger.warning(f"Tool {tool.name} has invalid parameters")
            return False

        if tool.parameters.get("type") != "object":
            logger.warning(f"Tool {tool.name} parameters must be type 'object'")
            return False

    return True
