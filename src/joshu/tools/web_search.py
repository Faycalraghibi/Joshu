"""
Web search tools for Joshu Assistant.
Provides functionality for searching the web and retrieving live information.
"""

from __future__ import annotations

import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)

# Try to import duckduckgo_search
try:
    from duckduckgo_search import DDGS
    DDGS_AVAILABLE = True
except ImportError:
    DDGS = None
    DDGS_AVAILABLE = False
    logger.warning("duckduckgo_search not available. Install with: pip install duckduckgo-search")


def search_web(
    query: str,
    max_results: int = 5,
    timeout: int = 10
) -> Dict[str, Any]:
    """
    Search the web using DuckDuckGo and return results.
    
    Args:
        query: Search query string
        max_results: Maximum number of results to return (default: 5)
        timeout: Timeout in seconds for the search request (default: 10)
        
    Returns:
        Dictionary containing:
            - success: bool indicating if search was successful
            - query: the original query
            - results: list of result dictionaries with 'title', 'url', 'snippet'
            - error: error message if success is False
    """
    if not DDGS_AVAILABLE:
        logger.error("DuckDuckGo search library not available")
        return {
            "success": False,
            "query": query,
            "results": [],
            "error": "duckduckgo_search library not installed. Install with: pip install duckduckgo-search"
        }
    
    if not query or not query.strip():
        logger.warning("Empty search query provided")
        return {
            "success": False,
            "query": query,
            "results": [],
            "error": "Search query cannot be empty"
        }
    
    try:
        logger.info(f"Searching web for: {query}")
        
        # Initialize DuckDuckGo search
        ddgs = DDGS()
        
        # Perform the search
        raw_results = ddgs.text(
            keywords=query,
            max_results=max_results,
            timelimit=None  # No time limit on results
        )
        
        # Parse and format results
        results = []
        for item in raw_results:
            result = {
                "title": item.get("title", "No title"),
                "url": item.get("href", item.get("link", "")),
                "snippet": item.get("body", item.get("description", "No description available"))
            }
            results.append(result)
        
        logger.info(f"Found {len(results)} results for query: {query}")
        
        return {
            "success": True,
            "query": query,
            "results": results,
            "error": None
        }
        
    except Exception as e:
        error_msg = f"Web search failed: {str(e)}"
        logger.error(error_msg)
        return {
            "success": False,
            "query": query,
            "results": [],
            "error": error_msg
        }


def format_search_results(search_response: Dict[str, Any]) -> str:
    """
    Format search results into a human-readable string.
    
    Args:
        search_response: Response dictionary from search_web()
        
    Returns:
        Formatted string representation of search results
    """
    if not search_response.get("success"):
        return f"Search failed: {search_response.get('error', 'Unknown error')}"
    
    results = search_response.get("results", [])
    if not results:
        return f"No results found for query: {search_response.get('query')}"
    
    output = [f"Search results for: {search_response.get('query')}\n"]
    
    for idx, result in enumerate(results, 1):
        output.append(f"{idx}. {result['title']}")
        output.append(f"   URL: {result['url']}")
        output.append(f"   {result['snippet']}\n")
    
    return "\n".join(output)
