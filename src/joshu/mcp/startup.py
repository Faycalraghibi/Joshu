"""Start the configured MCP servers and register their tools (once per process)."""

from __future__ import annotations

import logging
from typing import Callable, Optional

from joshu.mcp.loop import run as run_on_mcp_loop

logger = logging.getLogger(__name__)

_loaded = False


def load_mcp_tools(report: Optional[Callable[[str], None]] = None) -> int:
    """
    Connect to the MCP servers in config (and config/mcp.json) and register
    their tools with the agent's tool registry.

    Does nothing after the first call, when `mcp_enabled` is off, or (for
    discovery) when `mcp_discovery_on_startup` is off. Must not be called
    from inside a running event loop.

    Args:
        report: Receives a one-line summary when tools were registered

    Returns:
        Number of tools registered by this call.
    """
    global _loaded
    if _loaded:
        return 0
    _loaded = True

    from joshu.core.config import get_config_manager

    config = get_config_manager()
    if not config.get("mcp_enabled", True):
        return 0

    try:
        from joshu.mcp.discovery import register_mcp_tools_with_joshu
        from joshu.ui.cli_handlers.mcp_handler import load_mcp_servers_from_config

        load_mcp_servers_from_config()
        if not config.get("mcp_discovery_on_startup", True):
            return 0
        count = run_on_mcp_loop(register_mcp_tools_with_joshu())
    except Exception as e:
        logger.warning(f"MCP tool discovery failed: {e}")
        return 0

    if count and report is not None:
        report(f"[MCP] Registered {count} tools from MCP servers")
    return count


def reset() -> None:
    """Allow loading again (tests)."""
    global _loaded
    _loaded = False
