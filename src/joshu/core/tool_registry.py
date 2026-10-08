"""
Tool Registry System for Joshu.

This module provides a centralized registry for managing tools that can be called
by the LLM during conversations. Tools follow the OpenAI function calling format.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class ToolSpec:
    """
    Tool specification following OpenAI function calling format.

    Attributes:
        name: Unique identifier for the tool
        description: Human-readable description of what the tool does
        parameters: JSON schema describing the tool's parameters
        function: The actual callable function to execute
        enabled: Whether this tool is currently enabled
        requires_approval: Whether user approval is needed before execution
    """

    name: str
    description: str
    parameters: Dict[str, Any]
    function: Callable
    enabled: bool = True
    requires_approval: bool = False
    # Returns content from outside (MCP servers): marked as untrusted for the model
    external: bool = False

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

    def validate(self) -> bool:
        """Validate the tool specification."""
        if not self.name or not self.name.replace("_", "").isalnum():
            logger.error(f"Invalid tool name: {self.name}")
            return False

        if not self.description:
            logger.error(f"Tool {self.name} missing description")
            return False

        if not callable(self.function):
            logger.error(f"Tool {self.name} function is not callable")
            return False

        # Validate parameters schema
        if "type" not in self.parameters or self.parameters["type"] != "object":
            logger.error(f"Tool {self.name} parameters must be of type 'object'")
            return False

        return True


class ToolRegistry:
    """
    Central registry for managing available tools.

    This class maintains a collection of registered tools and provides
    methods for discovering, validating, and accessing them.
    """

    _instance: Optional[ToolRegistry] = None
    _tools: Dict[str, ToolSpec] = {}

    def __new__(cls) -> ToolRegistry:
        """Ensure singleton instance."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._tools = {}
        return cls._instance

    def register(self, tool: ToolSpec) -> bool:
        """
        Register a new tool.

        Args:
            tool: The tool specification to register

        Returns:
            True if registration successful, False otherwise
        """
        if not tool.validate():
            logger.error(f"Failed to register tool {tool.name}: validation failed")
            return False

        if tool.name in self._tools:
            logger.warning(f"Tool {tool.name} already registered, overwriting")

        self._tools[tool.name] = tool
        logger.info(f"Registered tool: {tool.name}")
        return True

    def unregister(self, tool_name: str) -> bool:
        """
        Unregister a tool.

        Args:
            tool_name: Name of the tool to unregister

        Returns:
            True if unregistration successful, False otherwise
        """
        if tool_name not in self._tools:
            logger.warning(f"Tool {tool_name} not found in registry")
            return False

        del self._tools[tool_name]
        logger.info(f"Unregistered tool: {tool_name}")
        return True

    def get_tool(self, tool_name: str) -> Optional[ToolSpec]:
        """
        Get a tool by name.

        Args:
            tool_name: Name of the tool

        Returns:
            The tool specification if found, None otherwise
        """
        return self._tools.get(tool_name)

    def get_available_tools(self, enabled_only: bool = True) -> List[ToolSpec]:
        """
        Get list of available tools.

        Args:
            enabled_only: If True, only return enabled tools

        Returns:
            List of tool specifications
        """
        if enabled_only:
            return [tool for tool in self._tools.values() if tool.enabled]
        return list(self._tools.values())

    def get_tools_for_llm(self, enabled_only: bool = True) -> List[Dict[str, Any]]:
        """
        Get tools in OpenAI function calling format for LLM.

        Args:
            enabled_only: If True, only return enabled tools

        Returns:
            List of tool specifications in OpenAI format
        """
        tools = self.get_available_tools(enabled_only=enabled_only)
        return [tool.to_openai_format() for tool in tools]

    def list_tools(self) -> List[str]:
        """
        Get list of all registered tool names.

        Returns:
            List of tool names
        """
        return list(self._tools.keys())

    def clear(self) -> None:
        """Clear all registered tools (mainly for testing)."""
        self._tools.clear()
        logger.info("Cleared all registered tools")


def register_tool(
    name: str,
    description: str,
    parameters: Dict[str, Any],
    enabled: bool = True,
    requires_approval: bool = False,
) -> Callable:
    """
    Decorator for registering a function as a tool.

    Args:
        name: Unique identifier for the tool
        description: Human-readable description
        parameters: JSON schema for parameters
        enabled: Whether the tool is enabled
        requires_approval: Whether user approval is needed

    Returns:
        Decorator function

    Example:
        @register_tool(
            name="web_search",
            description="Search the web for information",
            parameters={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"}
                },
                "required": ["query"]
            }
        )
        def search_web_tool(query: str) -> str:
            # Implementation
            pass
    """

    def decorator(func: Callable) -> Callable:
        tool = ToolSpec(
            name=name,
            description=description,
            parameters=parameters,
            function=func,
            enabled=enabled,
            requires_approval=requires_approval,
        )
        registry = ToolRegistry()
        registry.register(tool)
        return func

    return decorator


# Global registry instance
_registry = ToolRegistry()


def get_tool_registry() -> ToolRegistry:
    """Get the global tool registry instance."""
    return _registry


# Modules whose @register_tool decorators define the built-in tools
BUILTIN_TOOL_MODULES = (
    "joshu.tools.filesystem_tools",
    "joshu.tools.edit_tools",
    "joshu.tools.code_nav",
    "joshu.tools.shell_tool",
    "joshu.tools.todos",
    "joshu.tools.memory",
    "joshu.tools.implementations.web_search_tool",
    "joshu.tools.implementations.web_fetch_tool",
)


def load_builtin_tools() -> ToolRegistry:
    """
    Import the built-in tool modules so their tools are registered.

    Safe to call repeatedly; a module that fails to import is logged and skipped.
    """
    import importlib
    import sys

    # After clear() the modules are still cached, so re-run their decorators
    reload_needed = not _registry.list_tools()

    for module_name in BUILTIN_TOOL_MODULES:
        try:
            if reload_needed and module_name in sys.modules:
                importlib.reload(sys.modules[module_name])
            else:
                importlib.import_module(module_name)
        except Exception as e:
            logger.warning(f"Failed to load tools from {module_name}: {e}")
    return _registry
