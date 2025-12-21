"""
Hook system for agent lifecycle management.

This module provides a declarative hook system for intercepting
and modifying agent behavior at various stages of processing.

Key principles:
- ZERO execution logic - registers and fires hooks
- Pre/post processing at multiple stages
- Hooks can modify requests, responses, tool configs
- Priority-based hook ordering
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


class HookPhase(Enum):
    """Phase of the conversation lifecycle."""

    BEFORE_MODEL = "before_model"  # Before LLM request
    AFTER_MODEL = "after_model"  # After LLM response
    BEFORE_TOOL_SELECTION = "before_tool_selection"  # Before choosing tools
    AFTER_TOOL_SELECTION = "after_tool_selection"  # After tool selection
    BEFORE_TOOL_EXECUTION = "before_tool_execution"  # Before tool runs
    AFTER_TOOL_EXECUTION = "after_tool_execution"  # After tool completes
    BEFORE_AGENT = "before_agent"  # Before agent processing
    AFTER_AGENT = "after_agent"  # After agent processing
    ON_ERROR = "on_error"  # On any error
    ON_STREAM_CHUNK = "on_stream_chunk"  # On each stream chunk


@dataclass
class HookContext:
    """
    Context passed to hook handlers.

    Contains information about the current state and
    allows hooks to modify the processing flow.

    Attributes:
        phase: Current hook phase
        data: Phase-specific data (request, response, etc.)
        session_id: Current session identifier
        turn_number: Current conversation turn
        metadata: Additional context
        should_continue: Set to False to abort processing
        modified_data: Modified data to use instead
    """

    phase: HookPhase
    data: Any
    session_id: Optional[str] = None
    turn_number: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)
    should_continue: bool = True
    modified_data: Optional[Any] = None

    def modify(self, new_data: Any) -> None:
        """Set modified data for downstream processing."""
        self.modified_data = new_data

    def abort(self, reason: str = "") -> None:
        """Abort further processing."""
        self.should_continue = False
        self.metadata["abort_reason"] = reason

    def get_effective_data(self) -> Any:
        """Get data to use (modified or original)."""
        return self.modified_data if self.modified_data is not None else self.data


# Type for hook handlers
HookHandler = Callable[[HookContext], Optional[HookContext]]


@dataclass
class RegisteredHook:
    """
    A registered hook handler.

    Attributes:
        name: Hook identifier
        phase: Phase this hook handles
        handler: The handler function
        priority: Execution priority (higher = earlier)
        enabled: Whether hook is active
    """

    name: str
    phase: HookPhase
    handler: HookHandler
    priority: int = 0
    enabled: bool = True

    def __call__(self, context: HookContext) -> Optional[HookContext]:
        """Execute the hook handler."""
        if not self.enabled:
            return context
        return self.handler(context)


class HookRegistry:
    """
    Registry for managing hooks.

    Provides registration, deregistration, and execution
    of hooks at various lifecycle phases.

    Example:
        >>> registry = HookRegistry()
        >>> @registry.hook(HookPhase.BEFORE_MODEL)
        ... def log_request(ctx):
        ...     print(f"Request: {ctx.data}")
        ...     return ctx
    """

    def __init__(self) -> None:
        self._hooks: Dict[HookPhase, List[RegisteredHook]] = {phase: [] for phase in HookPhase}

    def register(
        self,
        name: str,
        phase: HookPhase,
        handler: HookHandler,
        priority: int = 0,
    ) -> RegisteredHook:
        """
        Register a hook handler.

        Args:
            name: Hook identifier
            phase: Phase to handle
            handler: Handler function
            priority: Execution priority

        Returns:
            RegisteredHook object
        """
        hook = RegisteredHook(
            name=name,
            phase=phase,
            handler=handler,
            priority=priority,
        )
        self._hooks[phase].append(hook)
        self._sort_hooks(phase)
        logger.debug(f"Registered hook '{name}' for phase {phase.value}")
        return hook

    def _sort_hooks(self, phase: HookPhase) -> None:
        """Sort hooks by priority (descending)."""
        self._hooks[phase].sort(key=lambda h: h.priority, reverse=True)

    def unregister(self, name: str, phase: Optional[HookPhase] = None) -> int:
        """
        Unregister hook(s) by name.

        Args:
            name: Hook name to remove
            phase: Optional phase to limit removal

        Returns:
            Number of hooks removed
        """
        count = 0
        phases = [phase] if phase else list(HookPhase)
        for p in phases:
            original = len(self._hooks[p])
            self._hooks[p] = [h for h in self._hooks[p] if h.name != name]
            count += original - len(self._hooks[p])
        return count

    def fire(
        self,
        phase: HookPhase,
        data: Any,
        session_id: Optional[str] = None,
        turn_number: int = 0,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> HookContext:
        """
        Fire all hooks for a phase.

        Args:
            phase: Phase to fire
            data: Data to pass to hooks
            session_id: Current session ID
            turn_number: Current turn number
            metadata: Additional context

        Returns:
            Final HookContext after all hooks
        """
        context = HookContext(
            phase=phase,
            data=data,
            session_id=session_id,
            turn_number=turn_number,
            metadata=metadata or {},
        )

        for hook in self._hooks[phase]:
            if not context.should_continue:
                logger.debug(f"Hook chain aborted at '{hook.name}'")
                break

            try:
                result = hook(context)
                if result is not None:
                    context = result
            except Exception as e:
                logger.error(f"Hook '{hook.name}' raised exception: {e}")
                context.metadata["hook_error"] = str(e)

        return context

    def hook(
        self,
        phase: HookPhase,
        priority: int = 0,
    ) -> Callable[[HookHandler], HookHandler]:
        """
        Decorator for registering hooks.

        Args:
            phase: Phase to handle
            priority: Execution priority

        Returns:
            Decorator function
        """

        def decorator(handler: HookHandler) -> HookHandler:
            name = handler.__name__
            self.register(name, phase, handler, priority)
            return handler

        return decorator

    def get_hooks(self, phase: HookPhase) -> List[RegisteredHook]:
        """Get all hooks for a phase."""
        return list(self._hooks[phase])

    def enable(self, name: str, enabled: bool = True) -> int:
        """Enable/disable hooks by name."""
        count = 0
        for hooks in self._hooks.values():
            for hook in hooks:
                if hook.name == name:
                    hook.enabled = enabled
                    count += 1
        return count

    def clear(self, phase: Optional[HookPhase] = None) -> None:
        """Clear all hooks for a phase (or all phases)."""
        if phase:
            self._hooks[phase].clear()
        else:
            for p in HookPhase:
                self._hooks[p].clear()


# Global hook registry
_registry: Optional[HookRegistry] = None


def get_hook_registry() -> HookRegistry:
    """Get the global hook registry."""
    global _registry
    if _registry is None:
        _registry = HookRegistry()
    return _registry


# Convenience functions for common hooks


def fire_before_model(data: Any, **kwargs: Any) -> HookContext:
    """Fire BEFORE_MODEL hooks."""
    return get_hook_registry().fire(HookPhase.BEFORE_MODEL, data, **kwargs)


def fire_after_model(data: Any, **kwargs: Any) -> HookContext:
    """Fire AFTER_MODEL hooks."""
    return get_hook_registry().fire(HookPhase.AFTER_MODEL, data, **kwargs)


def fire_before_tool_selection(data: Any, **kwargs: Any) -> HookContext:
    """Fire BEFORE_TOOL_SELECTION hooks."""
    return get_hook_registry().fire(HookPhase.BEFORE_TOOL_SELECTION, data, **kwargs)


def fire_after_tool_execution(data: Any, **kwargs: Any) -> HookContext:
    """Fire AFTER_TOOL_EXECUTION hooks."""
    return get_hook_registry().fire(HookPhase.AFTER_TOOL_EXECUTION, data, **kwargs)
