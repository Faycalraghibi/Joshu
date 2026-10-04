"""
Hook Dispatcher.

Executes hook scripts and manages hook registration.
"""

from __future__ import annotations

import json
import logging
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from joshu.hooks.events import HookEvent, HookExitCode
from joshu.hooks.schemas import HookPayload, HookResponse, HookResult

logger = logging.getLogger(__name__)

DEFAULT_HOOK_TIMEOUT = 10

# Events whose hooks may add context to the conversation with plain stdout
CONTEXT_EVENTS = {HookEvent.BEFORE_AGENT, HookEvent.SESSION_START}


@dataclass
class HookConfig:
    """Configuration for the hook system."""

    enabled: bool = True
    timeout: int = DEFAULT_HOOK_TIMEOUT
    hooks_dir: Optional[Path] = None

    hooks: Dict[HookEvent, List[Path]] = field(default_factory=dict)


@dataclass
class RegisteredHook:
    """A registered hook script."""

    event: HookEvent
    script_path: Path
    enabled: bool = True
    priority: int = 0  # Lower = runs first
    command: Optional[str] = None  # shell command; used instead of script_path when set
    timeout: Optional[int] = None  # seconds; falls back to the dispatcher timeout


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

        self._hooks[event].sort(key=lambda h: h.priority)

        logger.info(f"Registered hook for {event.value}: {script_path}")
        return True

    def register_command_hook(
        self, event: HookEvent, command: str, timeout: Optional[int] = None
    ) -> None:
        """Register a shell command as a hook (payload JSON on stdin)."""
        hook = RegisteredHook(
            event=event, script_path=Path(command), command=command, timeout=timeout
        )
        self._hooks.setdefault(event, []).append(hook)
        logger.info(f"Registered hook for {event.value}: {command}")

    def clear_script_hooks(self) -> None:
        """Remove all script and command hooks (Python hooks are kept)."""
        self._hooks.clear()

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

        script_hooks = self._hooks.get(event, [])
        python_hooks = self._python_hooks.get(event, [])

        if not script_hooks and not python_hooks:
            return HookResult(success=True, allowed=True)

        contexts: List[str] = []
        for handler in python_hooks:
            try:
                response = handler(payload)
                if response.additional_context:
                    contexts.append(response.additional_context)
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

        for hook in script_hooks:
            if not hook.enabled:
                continue

            result = self._execute_hook(hook, payload)

            if result.should_block:
                return result

            if result.modified_data:
                payload.data.update(result.modified_data)
            if result.context:
                contexts.append(result.context)

        return HookResult(
            success=True,
            allowed=True,
            response=HookResponse(
                action="allow",
                modified_data=payload.data if payload.data else None,
                additional_context="\n\n".join(contexts) or None,
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
            payload_json = json.dumps(payload.to_dict())

            if hook.command:
                argv: Any = hook.command
            elif hook.script_path.suffix == ".py":
                # .py files aren't directly executable on Windows
                argv = [sys.executable, str(hook.script_path)]
            else:
                argv = [str(hook.script_path)]

            result = subprocess.run(
                argv,
                shell=bool(hook.command),
                input=payload_json,
                capture_output=True,
                text=True,
                timeout=hook.timeout or self._config.timeout,
            )

            exit_code = result.returncode

            response = None
            if result.stdout.strip():
                try:
                    response_data = json.loads(result.stdout)
                    if not isinstance(response_data, dict):
                        raise json.JSONDecodeError("not an object", result.stdout, 0)
                    response = HookResponse.from_dict(response_data)
                except json.JSONDecodeError:
                    if payload.event in CONTEXT_EVENTS:
                        # Plain text from these hooks is context for the model
                        response = HookResponse(additional_context=result.stdout.strip()[:10000])
                    else:
                        logger.warning(f"Invalid JSON from hook: {result.stdout[:100]}")

            allowed = exit_code != HookExitCode.BLOCK
            if not allowed and (response is None or not response.message):
                # Exit code 2 without a JSON reason: stderr explains the block
                reason = result.stderr.strip()[:500] or None
                response = HookResponse(action="block", message=reason)

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


def dispatch_after_agent(session_id: str, prompt: str, response: str) -> HookResult:
    """Dispatch AFTER_AGENT event (the agent finished a request)."""
    payload = HookPayload(
        event=HookEvent.AFTER_AGENT,
        session_id=session_id,
        data={"prompt": prompt, "response": response},
    )
    return get_hook_dispatcher().dispatch(HookEvent.AFTER_AGENT, payload)


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


def dispatch_stop(session_id: str, prompt: str, response: str, continues: int) -> HookResult:
    """Dispatch STOP: the agent is about to finish; blocking sends it back to work."""
    payload = HookPayload(
        event=HookEvent.STOP,
        session_id=session_id,
        data={"prompt": prompt, "response": response, "continues_so_far": continues},
    )
    return get_hook_dispatcher().dispatch(HookEvent.STOP, payload)


def dispatch_subagent_stop(session_id: str, description: str, response: str) -> HookResult:
    """Dispatch SUBAGENT_STOP: a sub-agent finished its task."""
    payload = HookPayload(
        event=HookEvent.SUBAGENT_STOP,
        session_id=session_id,
        data={"description": description, "response": response},
    )
    return get_hook_dispatcher().dispatch(HookEvent.SUBAGENT_STOP, payload)


def dispatch_pre_compress(session_id: str, data: Dict[str, Any]) -> HookResult:
    """Dispatch PRE_COMPRESS: context is about to be cleared or summarized."""
    payload = HookPayload(event=HookEvent.PRE_COMPRESS, session_id=session_id, data=data)
    return get_hook_dispatcher().dispatch(HookEvent.PRE_COMPRESS, payload)


def dispatch_notification(session_id: str, message: str, data: Dict[str, Any]) -> HookResult:
    """Dispatch NOTIFICATION: Joshu needs the user (e.g. an approval)."""
    payload = HookPayload(
        event=HookEvent.NOTIFICATION,
        session_id=session_id,
        data={"message": message, **data},
    )
    return get_hook_dispatcher().dispatch(HookEvent.NOTIFICATION, payload)


def dispatch_session_end(session_id: str, data: Dict[str, Any]) -> HookResult:
    """Dispatch SESSION_END event."""
    payload = HookPayload(
        event=HookEvent.SESSION_END,
        session_id=session_id,
        data=data,
    )
    return get_hook_dispatcher().dispatch(HookEvent.SESSION_END, payload)


def configure_hooks_from_settings(settings: Dict[str, Any]) -> List[str]:
    """
    Register the hooks declared under `hooks:` in config.yaml.

    Replaces previously configured script/command hooks, so it is safe to call
    again after the configuration changes.

        hooks:
          before_tool:
            - python .joshu/hooks/check_tool.py
            - command: ./scripts/audit.sh
              timeout: 30

    Returns:
        Problems found (unknown events, malformed entries); valid entries are
        registered regardless.
    """
    dispatcher = get_hook_dispatcher()
    dispatcher.clear_script_hooks()
    problems: List[str] = []

    for event_name, entries in (settings or {}).items():
        try:
            event = HookEvent.from_string(str(event_name))
        except ValueError:
            valid = ", ".join(e.value for e in HookEvent)
            problems.append(f"unknown hook event '{event_name}' (valid: {valid})")
            continue

        if isinstance(entries, (str, dict)):
            entries = [entries]
        if not isinstance(entries, list):
            problems.append(f"hooks.{event_name} must be a list of commands")
            continue

        for entry in entries:
            if isinstance(entry, str) and entry.strip():
                dispatcher.register_command_hook(event, entry.strip())
            elif isinstance(entry, dict) and str(entry.get("command", "")).strip():
                timeout = entry.get("timeout")
                dispatcher.register_command_hook(
                    event,
                    str(entry["command"]).strip(),
                    timeout=timeout if isinstance(timeout, int) and timeout > 0 else None,
                )
            else:
                problems.append(f"hooks.{event_name}: invalid entry {entry!r}")

    for problem in problems:
        logger.warning(f"Hook configuration: {problem}")
    return problems
