"""
Tool Calling Helper Module.

This module provides utilities for tool calling integration with LLM conversations.
It handles backward compatibility with existing code while adding tool calling support.
"""

from __future__ import annotations

import logging
from typing import Any, Callable, Dict, List, Optional

from joshu.core.config import get_config_manager
from joshu.core.tool_executor import get_tool_executor
from joshu.core.tool_registry import get_tool_registry

logger = logging.getLogger(__name__)


def get_content_from_response(response: Any) -> str:
    """
     Extract text content from LLM response (backward compatible).

    Handles both old format (string) and new format (dict with 'content' key).

     Args:
         response: LLM response in old or new format

     Returns:
         Text content from response
    """
    if response is None:
        return ""

    if isinstance(response, dict):
        return response.get("content", "")

    # Old format - direct string
    return str(response)


def should_use_tool_calling() -> bool:
    """
    Check if tool calling is enabled in configuration.

    Returns:
        True if tool calling is enabled
    """
    try:
        config_manager = get_config_manager()
        return config_manager.get("tool_calling_enabled", True)
    except Exception as e:
        logger.warning(f"Failed to check tool calling config: {e}")
        return False  # Default to disabled if config check fails


def get_enabled_tools() -> List[Dict[str, Any]]:
    """
    Get list of enabled tools in OpenAI format for LLM.

    Returns:
        List of tool specifications
    """
    if not should_use_tool_calling():
        return []

    try:
        registry = get_tool_registry()
        return registry.get_tools_for_llm(enabled_only=True)
    except Exception as e:
        logger.error(f"Failed to get enabled tools: {e}")
        return []


def handle_tool_calls(
    tool_calls: List[Dict[str, Any]], max_iterations: Optional[int] = None
) -> List[Dict[str, Any]]:
    """
    Execute tool calls and format results for LLM.

    Args:
        tool_calls: List of tool calls from LLM response
        max_iterations: Maximum iterations to prevent infinite loops

    Returns:
        List of tool result messages for LLM
    """
    if not tool_calls:
        return []

    # Get max iterations from config if not specified
    if max_iterations is None:
        try:
            config_manager = get_config_manager()
            max_iterations = config_manager.get("tool_calling_max_iterations", 3)
        except Exception:
            max_iterations = 3

    executor = get_tool_executor()
    results = []

    for tool_call in tool_calls:
        try:
            # Execute the tool
            result = executor.execute_tool_call(tool_call)

            # Format result for LLM
            content = executor.format_result_for_llm(result)

            # Create tool result message
            tool_message = {
                "role": "tool",
                "tool_call_id": result.get("tool_call_id", ""),
                "content": content,
            }

            results.append(tool_message)

            logger.info(f"Tool {result.get('tool_name')} executed successfully")

        except Exception as e:
            logger.error(f"Failed to execute tool call: {e}", exc_info=True)
            # Add error result
            error_message = {
                "role": "tool",
                "tool_call_id": tool_call.get("id", ""),
                "content": f"Tool execution failed: {str(e)}",
            }
            results.append(error_message)

    return results


def chat_with_tools(
    messages: List[Dict[str, str]],
    chat_completion_func: Callable[..., Any],
    max_iterations: int = 3,
    **completion_kwargs: Any,
) -> Optional[Dict[str, Any]]:
    """
    Execute chat completion with automatic tool calling support.

    This function handles the tool calling loop:
    1. Call LLM with tools
    2. If LLM requests tools, execute them
    3. Send results back to LLM
    4. Repeat until LLM returns final response or max iterations reached

    Args:
        messages: Initial conversation messages
        chat_completion_func: Function to call for chat completion
        max_iterations: Maximum tool calling iterations
        **completion_kwargs: Additional arguments for chat completion

    Returns:
        Final LLM response dictionary
    """
    if not should_use_tool_calling():
        # Tool calling disabled, just do normal completion
        return chat_completion_func(messages=messages, **completion_kwargs)

    # Get available tools
    tools = get_enabled_tools()
    if not tools:
        # No tools available, just do normal completion
        return chat_completion_func(messages=messages, **completion_kwargs)

    # Add tools to completion kwargs
    completion_kwargs["tools"] = tools

    iteration = 0
    current_messages = messages.copy()

    while iteration < max_iterations:
        # Call LLM
        response = chat_completion_func(messages=current_messages, **completion_kwargs)

        if not response:
            return None

        # Check if there are tool calls
        tool_calls = response.get("tool_calls")

        if not tool_calls:
            # No tool calls, return final response
            return response

        # LLM requested tool calls
        logger.info(f"LLM requested {len(tool_calls)} tool calls")

        # Add assistant message with tool calls to conversation
        assistant_message = {
            "role": "assistant",
            "content": response.get("content", ""),
            "tool_calls": tool_calls,
        }
        current_messages.append(assistant_message)

        # Execute tools and get results
        tool_results = handle_tool_calls(tool_calls, max_iterations)

        # Add tool results to conversation
        current_messages.extend(tool_results)

        iteration += 1

    # Max iterations reached, do one final call to get response
    logger.warning(f"Max tool calling iterations ({max_iterations}) reached")

    # Remove tools for final call to force LLM to give final answer
    final_kwargs = completion_kwargs.copy()
    final_kwargs.pop("tools", None)

    return chat_completion_func(messages=current_messages, **final_kwargs)
