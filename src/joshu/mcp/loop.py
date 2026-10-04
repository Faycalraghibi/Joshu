"""
One event loop for all MCP communication.

MCP transports keep asyncio streams (stdio subprocess pipes, HTTP clients)
that belong to the event loop they were created in. Running each call with a
fresh `asyncio.run()` connected a server in one loop and then talked to it
from another, closed one, so every tool call after discovery failed. All MCP
work now runs on this single background loop, which lives as long as the
process.
"""

from __future__ import annotations

import asyncio
import atexit
import threading
from typing import Any, Awaitable, Optional, TypeVar

T = TypeVar("T")

DEFAULT_TIMEOUT = 300.0

_loop: Optional[asyncio.AbstractEventLoop] = None
_lock = threading.Lock()


def _get_loop() -> asyncio.AbstractEventLoop:
    global _loop
    with _lock:
        if _loop is None or _loop.is_closed():
            _loop = asyncio.new_event_loop()
            thread = threading.Thread(target=_loop.run_forever, name="joshu-mcp", daemon=True)
            thread.start()
            atexit.register(_shutdown)
        return _loop


def run(coro: Awaitable[T], timeout: Optional[float] = DEFAULT_TIMEOUT) -> T:
    """Run an MCP coroutine on the shared loop and wait for its result."""
    loop = _get_loop()
    try:
        running = asyncio.get_running_loop()
    except RuntimeError:
        running = None
    if running is loop:
        raise RuntimeError("joshu.mcp.loop.run() called from the MCP loop itself; await instead")
    future = asyncio.run_coroutine_threadsafe(coro, loop)  # type: ignore[arg-type]
    return future.result(timeout)


def _shutdown() -> None:
    """Disconnect servers (ends stdio subprocesses) and stop the loop."""
    loop = _loop
    if loop is None or loop.is_closed():
        return
    future = None
    try:
        from joshu.mcp.registry import get_mcp_registry

        future = asyncio.run_coroutine_threadsafe(get_mcp_registry().disconnect_all(), loop)
        future.result(8)
    except Exception:
        # Too slow: cancel it rather than leave a pending task behind, which
        # asyncio reports as "Task was destroyed but it is pending" at exit
        if future is not None:
            future.cancel()
    loop.call_soon_threadsafe(loop.stop)


def reset() -> None:
    """Stop the loop (tests); the next call starts a new one."""
    global _loop
    _shutdown()
    _loop = None


__all__: Any = ["run", "reset"]
