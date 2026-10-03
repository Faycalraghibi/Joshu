"""
Joshu Hook System.

Provides lifecycle hooks for customizing agent behavior.
Hooks are external scripts that intercept and modify agent actions.
"""

from joshu.hooks.dispatcher import (
    HookDispatcher,
    configure_hooks_from_settings,
    get_hook_dispatcher,
)
from joshu.hooks.events import HookEvent
from joshu.hooks.schemas import HookPayload, HookResponse, HookResult

__all__ = [
    "HookEvent",
    "HookPayload",
    "HookResponse",
    "HookResult",
    "HookDispatcher",
    "get_hook_dispatcher",
    "configure_hooks_from_settings",
]
