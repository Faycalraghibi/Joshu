"""
Hook Dispatcher.

Executes hook scripts and manages hook registration.
"""

from __future__ import annotations

import json
import logging
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from joshu.hooks.events import HookEvent, HookExitCode
from joshu.hooks.schemas import HookPayload, HookResponse, HookResult

logger = logging.getLogger(__name__)

# Default timeout for hook execution (seconds)
DEFAULT_HOOK_TIMEOUT = 10


@dataclass
class HookConfig:
    """Configuration for the hook system."""

    enabled: bool = True
    timeout: int = DEFAULT_HOOK_TIMEOUT
    hooks_dir: Optional[Path] = None

    # Per-event hooks (script paths)
    hooks: Dict[HookEvent, List[Path]] = field(default_factory=dict)


@dataclass
class RegisteredHook:
    """A registered hook script."""

    event: HookEvent
    script_path: Path
    enabled: bool = True
    priority: int = 0  # Lower = runs first


class HookDispatcher:
    """
    Dispatches events to registered hook scripts.

    Hook scripts communicate via:
    - stdin: JSON payload with event data
    - stdout: JSON response with modifications
    - exit code: 0=allow, 2=block, other=warn
    """

    _instance: Optional["HookDispatcher"] = None

    def __new__(cls) -> "HookDispatcher":
        """Ensure singleton instance."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._hooks = {}
            cls._instance._config = HookConfig()
            cls._instance._python_hooks = {}
        return cls._instance

    def __init__(self):
        """Initialize the dispatcher."""
        if not hasattr(self, "_initialized"):
            self._hooks: Dict[HookEvent, List[RegisteredHook]] = {}
            self._config = HookConfig()
            self._python_hooks: Dict[HookEvent, List[Callable]] = {}
            self._initialized = True

    @property
    def config(self) -> HookConfig:
        """Get hook configuration."""
        return self._config

    def configure(self, config: HookConfig) -> None:
        """Set hook configuration."""
        self._config = config

        # Register hooks from config
        for event, paths in config.hooks.items():
            for path in paths:
                self.register_hook(event, path)

    def register_hook(
        self,
        event: HookEvent,
        script_path: Path,
        priority: int = 0,
    ) -> bool:
        """
        Register a hook script for an event.

        Args:
            event: Event to hook
            script_path: Path to hook script
            priority: Execution priority (lower = first)

        Returns:
            True if registration successful
        """
        if not script_path.exists():
            logger.warning(f"Hook script not found: {script_path}")
            return False

        if event not in self._hooks:
            self._hooks[event] = []

        hook = RegisteredHook(
            event=event,
            script_path=script_path,
            priority=priority,
        )
        self._hooks[event].append(hook)

        # Sort by priority
        self._hooks[event].sort(key=lambda h: h.priority)

        logger.info(f"Registered hook for {event.value}: {script_path}")
        return True

    def register_python_hook(
        self,
        event: HookEvent,
        handler: Callable[[HookPayload], HookResponse],
    ) -> None:
        """
        Register a Python function as a hook.

        Args:
            event: Event to hook
            handler: Handler function
        """
        if event not in self._python_hooks:
            self._python_hooks[event] = []
        self._python_hooks[event].append(handler)
        logger.info(f"Registered Python hook for {event.value}")

    def unregister_hook(self, event: HookEvent, script_path: Path) -> bool:
        """
        Unregister a hook script.

        Args:
            event: Event type
            script_path: Path to hook script

        Returns:
            True if unregistered successfully
        """
        if event not in self._hooks:
            return False

        original_len = len(self._hooks[event])
        self._hooks[event] = [h for h in self._hooks[event] if h.script_path != script_path]

        return len(self._hooks[event]) < original_len

    def dispatch(
        self,
        event: HookEvent,
        payload: HookPayload,
    ) -> HookResult:
        """
        Dispatch an event to all registered hooks.

        Args:
            event: Event to dispatch
            payload: Event payload

        Returns:
            Combined result from all hooks
        """
        if not self._config.enabled:
            return HookResult(success=True, allowed=True)

        # Get all hooks for this event
        script_hooks = self._hooks.get(event, [])
        python_hooks = self._python_hooks.get(event, [])

        if not script_hooks and not python_hooks:
            return HookResult(success=True, allowed=True)

        # Execute Python hooks first
        for handler in python_hooks:
            try:
                response = handler(payload)
                if response.action == "block":
                    return HookResult(
                        success=True,
                        allowed=False,
                        response=response,
                    )
                if response.action == "modify" and response.modified_data:
                    payload.data.update(response.modified_data)
            except Exception as e:
                logger.error(f"Python hook error: {e}")

        # Execute script hooks
        for hook in script_hooks:
            if not hook.enabled:
                continue

            result = self._execute_hook(hook, payload)

            # If hook blocks, stop execution
            if result.should_block:
                return result

            # Apply modifications to payload for next hook
            if result.modified_data:
                payload.data.update(result.modified_data)

        return HookResult(
            success=True,
            allowed=True,
            response=HookResponse(
                action="allow",
                modified_data=payload.data if payload.data else None,
            ),
        )

    def _execute_hook(
        self,
        hook: RegisteredHook,
        payload: HookPayload,
    ) -> HookResult:
        """
        Execute a single hook script.

        Args:
            hook: Hook to execute
            payload: Event payload

        Returns:
            Hook result
        """
        try:
            # Serialize payload to JSON
            payload_json = json.dumps(payload.to_dict())

            # Execute hook script
            result = subprocess.run(
                [str(hook.script_path)],
                input=payload_json,
                capture_output=True,
                text=True,
                timeout=self._config.timeout,
            )

            exit_code = result.returncode

            # Parse response from stdout
            response = None
            if result.stdout.strip():
                try:
                    response_data = json.loads(result.stdout)
                    response = HookResponse.from_dict(response_data)
                except json.JSONDecodeError:
                    logger.warning(f"Invalid JSON from hook: {result.stdout[:100]}")

            # Determine if blocked based on exit code
            allowed = exit_code != HookExitCode.BLOCK

            # Log warnings for non-standard exit codes
            if exit_code not in (HookExitCode.ALLOW, HookExitCode.BLOCK):
                logger.warning(f"Hook {hook.script_path} exited with code {exit_code}")
                if result.stderr:
                    logger.warning(f"Hook stderr: {result.stderr[:200]}")

            return HookResult(
                success=True,
                allowed=allowed,
                response=response,
                exit_code=exit_code,
            )

        except subprocess.TimeoutExpired:
            logger.error(f"Hook timed out: {hook.script_path}")
            return HookResult(
                success=False,
                allowed=True,  # Allow on timeout (fail-open)
                error="Hook execution timed out",
            )
        except Exception as e:
            logger.error(f"Hook execution error: {e}")
            return HookResult(
                success=False,
                allowed=True,  # Allow on error (fail-open)
                error=str(e),
            )

    def list_hooks(self, event: Optional[HookEvent] = None) -> Dict[str, List[str]]:
        """
        List registered hooks.

        Args:
            event: Filter by event (optional)

        Returns:
            Dict mapping event names to hook paths
        """
        result = {}

        events = [event] if event else list(HookEvent)

        for e in events:
            hooks = self._hooks.get(e, [])
            if hooks:
                result[e.value] = [str(h.script_path) for h in hooks]

        return result

    def clear(self) -> None:
        """Clear all registered hooks."""
        self._hooks.clear()
        self._python_hooks.clear()
        logger.info("Cleared all hooks")


# Global dispatcher instance
_dispatcher: Optional[HookDispatcher] = None


def get_hook_dispatcher() -> HookDispatcher:
    """
    Get the global hook dispatcher instance.

    Returns:
        HookDispatcher singleton
    """
    global _dispatcher
    if _dispatcher is None:
        _dispatcher = HookDispatcher()
    return _dispatcher


# Convenience functions for common events


def dispatch_session_start(session_id: str, data: Dict[str, Any]) -> HookResult:
    """Dispatch SESSION_START event."""
    payload = HookPayload(
        event=HookEvent.SESSION_START,
        session_id=session_id,
        data=data,
    )
    return get_hook_dispatcher().dispatch(HookEvent.SESSION_START, payload)


def dispatch_before_agent(
    session_id: str,
    prompt: str,
    context: str = "",
) -> HookResult:
    """Dispatch BEFORE_AGENT event."""
    payload = HookPayload(
        event=HookEvent.BEFORE_AGENT,
        session_id=session_id,
        data={"prompt": prompt, "context": context},
    )
    return get_hook_dispatcher().dispatch(HookEvent.BEFORE_AGENT, payload)


def dispatch_before_tool(
    session_id: str,
    tool_name: str,
    arguments: Dict[str, Any],
) -> HookResult:
    """Dispatch BEFORE_TOOL event."""
    payload = HookPayload(
        event=HookEvent.BEFORE_TOOL,
        session_id=session_id,
        data={"tool_name": tool_name, "arguments": arguments},
    )
    return get_hook_dispatcher().dispatch(HookEvent.BEFORE_TOOL, payload)


def dispatch_after_tool(
    session_id: str,
    tool_name: str,
    result: Any,
    success: bool = True,
) -> HookResult:
    """Dispatch AFTER_TOOL event."""
    payload = HookPayload(
        event=HookEvent.AFTER_TOOL,
        session_id=session_id,
        data={
            "tool_name": tool_name,
            "result": result,
            "success": success,
        },
    )
    return get_hook_dispatcher().dispatch(HookEvent.AFTER_TOOL, payload)


def dispatch_session_end(session_id: str, data: Dict[str, Any]) -> HookResult:
    """Dispatch SESSION_END event."""
    payload = HookPayload(
        event=HookEvent.SESSION_END,
        session_id=session_id,
        data=data,
    )
    return get_hook_dispatcher().dispatch(HookEvent.SESSION_END, payload)
