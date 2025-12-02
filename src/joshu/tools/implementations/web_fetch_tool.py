"""
Web Fetch Tool Implementation.

This module provides the web fetch tool that can be called by the LLM
to retrieve and process content from URLs.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from joshu.core.config import get_config_manager
from joshu.core.tool_registry import register_tool
from joshu.tools.web_fetch import process_url_content

logger = logging.getLogger(__name__)


# Define the web fetch tool specification
WEB_FETCH_TOOL_SPEC = {
    "type": "object",
    "properties": {
        "url": {
            "type": "string",
            "description": "The URL to fetch content from (must be HTTP or HTTPS)",
        },
        "instruction": {
            "type": "string",
            "description": "Optional instruction for how to process the content (e.g., 'summarize', 'extract main points', 'find information about X')",
        },
    },
    "required": ["url"],
}


@register_tool(
    name="web_fetch",
    description="""Fetch and process content from a URL. Use this when you need to:
- Read the contents of a specific web page
- Extract information from a URL the user provides
- Summarize or analyze content from a website
- Compare content from multiple URLs

This tool retrieves the actual content of web pages and converts it to readable text.
For searching the web to find URLs, use web_search instead.""",
    parameters=WEB_FETCH_TOOL_SPEC,
    enabled=True,
    requires_approval=True,  # Security: user must confirm before accessing URLs
)
def web_fetch_tool(url: str, instruction: Optional[str] = None) -> Dict[str, Any]:
    """
    Fetch and process content from a URL.

    This function is registered as a tool that can be called by the LLM.
    It requires user approval before execution for security.

    Args:
        url: The URL to fetch content from
        instruction: Optional instruction for processing the content

    Returns:
        Dictionary containing:
            - success: bool indicating if fetch was successful
            - url: the original URL
            - source: source attribution (same as URL)
            - content: the fetched and processed content
            - instruction: the processing instruction (if provided)
            - truncated: bool indicating if content was truncated
            - error: error message if success is False
    """
    logger.info(f"Web fetch tool called with URL: {url}")

    # Get configuration
    config_manager = get_config_manager()

    # Check if web fetch is enabled
    if not config_manager.get("web_fetch_enabled", True):
        logger.warning("Web fetch is disabled in configuration")
        return {
            "success": False,
            "url": url,
            "source": url,
            "content": None,
            "instruction": instruction,
            "truncated": False,
            "error": "Web fetch is disabled in configuration",
        }

    # Get configuration values
    timeout = config_manager.get("web_fetch_timeout", 15)
    max_length = config_manager.get("web_fetch_max_content_length", 50000)

    # Process the URL content
    try:
        result = process_url_content(
            url=url,
            instruction=instruction,
            max_length=max_length,
            timeout=timeout,
        )

        if result["success"]:
            logger.info(
                f"Web fetch completed: {len(result.get('content', '') or '')} chars"
                f"{' (truncated)' if result.get('truncated') else ''}"
            )
        else:
            logger.warning(f"Web fetch failed: {result.get('error')}")

        return result

    except Exception as e:
        logger.error(f"Web fetch tool error: {e}", exc_info=True)
        return {
            "success": False,
            "url": url,
            "source": url,
            "content": None,
            "instruction": instruction,
            "truncated": False,
            "error": f"Fetch failed: {str(e)}",
        }
