"""
Tool Executor for Joshu.

This module provides safe execution of registered tools with error handling,
logging, and result formatting for LLM consumption.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, Optional

from joshu.core.tool_registry import ToolRegistry

logger = logging.getLogger(__name__)


class ToolExecutionError(Exception):
    """Exception raised when tool execution fails."""

    pass


class ToolExecutor:
    """
    Handles execution of registered tools.

    This class manages the invocation of tools, including error handling,
    logging, and result formatting.
    """

    def __init__(self, registry: Optional[ToolRegistry] = None):
        """
        Initialize the tool executor.

        Args:
            registry: Tool registry to use (defaults to global registry)
        """
        self.registry = registry or ToolRegistry()

    def execute_tool(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Execute a tool with the given arguments.

        Args:
            tool_name: Name of the tool to execute
            arguments: Dictionary of arguments to pass to the tool

        Returns:
            Dictionary containing:
                - success: bool indicating if execution was successful
                - result: The tool's return value (if successful)
                - error: Error message (if failed)

        Raises:
            ToolExecutionError: If tool not found or disabled
        """
        logger.info(f"Executing tool: {tool_name} with arguments: {arguments}")

        # Get the tool
        tool = self.registry.get_tool(tool_name)
        if tool is None:
            error_msg = f"Tool not found: {tool_name}"
            logger.error(error_msg)
            raise ToolExecutionError(error_msg)

        if not tool.enabled:
            error_msg = f"Tool is disabled: {tool_name}"
            logger.error(error_msg)
            raise ToolExecutionError(error_msg)

        # Execute the tool
        try:
            result = tool.function(**arguments)
            logger.info(f"Tool {tool_name} executed successfully")
            return {
                "success": True,
                "result": result,
                "error": None,
            }
        except TypeError as e:
            error_msg = f"Invalid arguments for tool {tool_name}: {str(e)}"
            logger.error(error_msg)
            return {
                "success": False,
                "result": None,
                "error": error_msg,
            }
        except Exception as e:
            error_msg = f"Tool execution failed: {str(e)}"
            logger.error(f"Error executing tool {tool_name}: {e}", exc_info=True)
            return {
                "success": False,
                "result": None,
                "error": error_msg,
            }

    def format_result_for_llm(self, result: Dict[str, Any]) -> str:
        """
        Format tool execution result for LLM consumption.

        Args:
            result: Tool execution result dictionary

        Returns:
            Formatted string suitable for LLM context
        """
        if result["success"]:
            # Format successful result
            tool_result = result["result"]

            # If result is already a string, return it
            if isinstance(tool_result, str):
                return tool_result

            # If result is a dict, try to extract meaningful content
            if isinstance(tool_result, dict):
                # For search results, format nicely
                if "results" in tool_result and isinstance(tool_result["results"], list):
                    return self._format_search_results(tool_result)
                # Otherwise compact JSON: indentation costs tokens on every later request
                return json.dumps(tool_result, ensure_ascii=False, default=str)

            # For other types, convert to string
            return str(tool_result)
        else:
            # Format error
            return f"Tool execution failed: {result['error']}"

    def _format_search_results(self, search_result: Dict[str, Any]) -> str:
        """
        Format search results for LLM consumption.

        Args:
            search_result: Search result dictionary

        Returns:
            Formatted string
        """
        if not search_result.get("success"):
            return f"Search failed: {search_result.get('error', 'Unknown error')}"

        results = search_result.get("results", [])
        if not results:
            return f"No results found for query: {search_result.get('query', '')}"

        formatted = [f"Search results for '{search_result.get('query', '')}':\n"]

        for idx, item in enumerate(results, 1):
            title = item.get("title", "No title")
            url = item.get("url", "")
            snippet = item.get("snippet", "No description")

            formatted.append(f"{idx}. {title}")
            formatted.append(f"   URL: {url}")
            formatted.append(f"   {snippet}\n")

        return "\n".join(formatted)

    def execute_tool_call(
        self,
        tool_call: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Execute a tool call from LLM response.

        This method parses a tool call in OpenAI format and executes it.

        Args:
            tool_call: Tool call dictionary from LLM response in format:
                {
                    "id": "call_xyz",
                    "type": "function",
                    "function": {
                        "name": "tool_name",
                        "arguments": "{\"arg\": \"value\"}"
                    }
                }

        Returns:
            Dictionary containing execution result
        """
        try:
            # Extract tool name and arguments
            function_data = tool_call.get("function", {})
            tool_name = function_data.get("name")
            arguments_str = function_data.get("arguments", "{}")

            if not tool_name:
                raise ToolExecutionError("Tool call missing function name")

            # Parse arguments (they come as JSON string)
            try:
                arguments = json.loads(arguments_str)
            except json.JSONDecodeError as e:
                raise ToolExecutionError(f"Invalid arguments JSON: {str(e)}")

            # Execute the tool
            result = self.execute_tool(tool_name, arguments)

            # Add tool call ID to result
            result["tool_call_id"] = tool_call.get("id")
            result["tool_name"] = tool_name

            return result

        except Exception as e:
            logger.error(f"Error parsing tool call: {e}", exc_info=True)
            return {
                "success": False,
                "result": None,
                "error": str(e),
                "tool_call_id": tool_call.get("id"),
                "tool_name": tool_call.get("function", {}).get("name", "unknown"),
            }


# Global executor instance
_executor = ToolExecutor()


def get_tool_executor() -> ToolExecutor:
    """Get the global tool executor instance."""
    return _executor
