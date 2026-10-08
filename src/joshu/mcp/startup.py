"""Start the configured MCP servers and register their tools (once per process)."""

from __future__ import annotations

import logging
import threading
from typing import Callable, List, Optional

from joshu.mcp.loop import run as run_on_mcp_loop

logger = logging.getLogger(__name__)

_loaded = False
# Loading started by load_mcp_tools_in_background, and what it reported
_background: Optional[threading.Thread] = None
background_report: List[str] = []


def load_mcp_tools_in_background() -> None:
    """
    Start the MCP servers on a thread, so the prompt doesn't wait for them;
    load_mcp_tools (when the agent is created) waits for it to finish.
    """
    global _background
    if _loaded or _background is not None:
        return
    _background = threading.Thread(
        target=load_mcp_tools, kwargs={"report": background_report.append}, daemon=True
    )
    _background.start()


def mcp_loading() -> bool:
    """MCP servers are still starting in the background."""
    return _background is not None and _background.is_alive()


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
    if _background is not None and _background is not threading.current_thread():
        _background.join()  # started at startup: wait for it, don't start again
        return 0
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


def load_new_mcp_servers(report: Optional[Callable[[str], None]] = None) -> int:
    """
    Start the MCP servers configured since startup (a plugin installed in the
    session) and register their tools; the running ones are left alone.

    Returns:
        Number of tools registered.
    """
    from joshu.core.config import get_config_manager

    if not get_config_manager().get("mcp_enabled", True):
        return 0
    try:
        from joshu.mcp.discovery import register_mcp_tools_with_joshu
        from joshu.mcp.registry import get_mcp_registry
        from joshu.ui.cli_handlers.mcp_handler import load_mcp_servers_from_config

        registry = get_mcp_registry()
        before = {server.name for server in registry.list_servers()}
        load_mcp_servers_from_config()
        new = [s.name for s in registry.list_servers() if s.name not in before]
        if not new:
            return 0
        count = run_on_mcp_loop(register_mcp_tools_with_joshu(servers=new))
    except Exception as e:
        logger.warning(f"Starting new MCP servers failed: {e}")
        return 0
    if report is not None:
        report(f"[MCP] Started {', '.join(new)}: {count} tools")
    return count


def reset() -> None:
    """Allow loading again (tests)."""
    global _loaded, _background
    _loaded = False
    _background = None
    background_report.clear()
