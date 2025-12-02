"""
Search command handler for Joshu CLI.
Provides web search functionality through DuckDuckGo.
"""

from __future__ import annotations

import logging
from typing import Optional

from rich.console import Console
from rich.panel import Panel

from joshu.core.config import get_config_manager
from joshu.tools.web_search import DDGS_AVAILABLE, search_web

logger = logging.getLogger(__name__)
console = Console()


def handle_search_command(query: str, max_results: Optional[int] = None) -> None:
    """
    Handle the search command from CLI.

    Args:
        query: Search query string
        max_results: Optional maximum number of results to show (overrides config)
    """
    # Get configuration
    config_manager = get_config_manager()

    # Check if web search is enabled
    if not config_manager.get("web_search_enabled", True):
        console.print("[yellow]⚠[/yellow] Web search is disabled in configuration.")
        console.print(
            "[dim]Enable it with:[/dim] [cyan]joshu config --set web_search_enabled=true[/cyan]"
        )
        return

    # Check if library is available
    if not DDGS_AVAILABLE:
        console.print("[red]✗[/red] Web search library not installed.")
        console.print("[dim]Install with:[/dim] [cyan]pip install ddgs[/cyan]")
        console.print(
            "[dim]Or:[/dim] [cyan]pip install -e .[/cyan] [dim]to install all dependencies[/dim]"
        )
        return

    # Get max results from config or parameter
    if max_results is None:
        max_results = config_manager.get("web_search_max_results", 5)

    # Get timeout from config
    timeout = config_manager.get("web_search_timeout", 10)

    # Display search indicator
    console.print(f"[bold]🔍 Searching for:[/bold] {query}")
    console.print()

    # Perform search
    try:
        with console.status("[bold cyan]Searching the web...", spinner="dots"):
            result = search_web(query, max_results=max_results, timeout=timeout)
    except Exception as e:
        console.print(f"[red]✗ Search failed:[/red] {str(e)}")
        logger.error(f"Search error: {e}", exc_info=True)
        return

    # Handle search failure
    if not result.get("success"):
        error_msg = result.get("error", "Unknown error")
        console.print(f"[red]✗ Search failed:[/red] {error_msg}")
        return

    # Get results
    results = result.get("results", [])

    if not results:
        console.print(f"[yellow]No results found for:[/yellow] {query}")
        console.print("[dim]Try rephrasing your search query or using different keywords.[/dim]")
        return

    # Display results
    console.print(
        f"[bold green]✓[/bold green] Found {len(results)} result{'s' if len(results) != 1 else ''}:"
    )
    console.print()

    for idx, item in enumerate(results, 1):
        title = item.get("title", "No title")
        url = item.get("url", "")
        snippet = item.get("snippet", "No description available")

        # Create a panel for each result
        panel_content = f"[bold]{title}[/bold]\n"
        panel_content += f"[dim]{url}[/dim]\n\n"
        panel_content += f"{snippet}"

        panel = Panel(
            panel_content, title=f"[cyan]Result {idx}[/cyan]", border_style="blue", padding=(0, 1)
        )

        console.print(panel)
        console.print()

    # Show helpful tip
    console.print(
        "[dim]💡 Tip: Use [cyan]--max-results N[/cyan] to show more or fewer results[/dim]"
    )


def format_search_results_for_agent(search_response: dict) -> str:
    """
    Format search results for use in agent context.

    This is a simplified version for agent/LLM consumption.

    Args:
        search_response: Response dictionary from search_web()

    Returns:
        Formatted string suitable for LLM context
    """
    if not search_response.get("success"):
        return f"Search failed: {search_response.get('error', 'Unknown error')}"

    results = search_response.get("results", [])
    if not results:
        return f"No results found for: {search_response.get('query')}"

    output = []
    output.append(f"Search results for '{search_response.get('query')}':\n")

    for idx, result in enumerate(results, 1):
        output.append(f"{idx}. {result['title']}")
        output.append(f"   {result['snippet']}")
        output.append(f"   URL: {result['url']}\n")

    return "\n".join(output)
