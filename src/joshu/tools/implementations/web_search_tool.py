"""
Web Search Tool Implementation.

This module provides the web search tool that can be called by the LLM.
"""

from __future__ import annotations

import logging
from typing import Any, Dict

from joshu.core.config import get_config_manager
from joshu.core.tool_registry import register_tool
from joshu.tools.web_search import search_web

logger = logging.getLogger(__name__)


# Define the web search tool specification
WEB_SEARCH_TOOL_SPEC = {
    "type": "object",
    "properties": {
        "query": {"type": "string", "description": "The search query to look up on the web"},
        "max_results": {
            "type": "integer",
            "description": "Maximum number of search results to return (default: 5)",
            "default": 5,
        },
    },
    "required": ["query"],
}


@register_tool(
    name="web_search",
    description="Search the web for current information, news, documentation, or any topic that requires up-to-date knowledge. Use this when you need information beyond your training data or when the user asks about current events, latest versions, or real-time information.",
    parameters=WEB_SEARCH_TOOL_SPEC,
    enabled=True,
    requires_approval=False,
)
def web_search_tool(query: str, max_results: int = 5) -> Dict[str, Any]:
    """
    Execute a web search.

    This function is registered as a tool that can be called by the LLM.

    Args:
        query: The search query
        max_results: Maximum number of results to return

    Returns:
        Dictionary containing search results
    """
    logger.info(f"Web search tool called with query: {query}")

    # Get configuration
    config_manager = get_config_manager()

    # Check if web search is enabled
    if not config_manager.get("web_search_enabled", True):
        logger.warning("Web search is disabled in configuration")
        return {
            "success": False,
            "query": query,
            "results": [],
            "error": "Web search is disabled in configuration",
        }

    # Get timeout from config
    timeout = config_manager.get("web_search_timeout", 10)

    # Use config max_results if not specified
    if max_results is None or max_results <= 0:
        max_results = config_manager.get("web_search_max_results", 5)

    # Perform the search
    try:
        result = search_web(query, max_results=max_results, timeout=timeout)
        logger.info(f"Web search completed: found {len(result.get('results', []))} results")
        return result
    except Exception as e:
        logger.error(f"Web search tool error: {e}", exc_info=True)
        return {
            "success": False,
            "query": query,
            "results": [],
            "error": f"Search failed: {str(e)}",
        }
