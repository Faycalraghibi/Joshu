"""
The agent loop.

Assemble context → call the model with tools → run each requested tool through
the permission gate and hooks → feed results back → repeat until the model
answers without calling a tool (or the turn limit is reached).
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from joshu.core.checkpoints import Checkpoint, CheckpointStore
from joshu.core.compaction import compact_messages, estimate_tokens
from joshu.core.config import get_config_manager
from joshu.core.costs import CostTracker, request_cost
from joshu.core.images import build_user_content
from joshu.core.llm_client import (
    AssistantTurn,
    ChatClient,
    ToolCall,
    create_chat_client,
)
from joshu.core.permissions import EDIT_TOOLS, PermissionManager, PermissionMode
from joshu.core.subagents import SubagentSpec, discover_subagents
from joshu.core.system_prompt import build_subagent_prompt, build_system_prompt
from joshu.core.tool_executor import ToolExecutor
from joshu.core.tool_registry import ToolSpec, load_builtin_tools

logger = logging.getLogger(__name__)

SUBAGENT_MAX_TURNS = 25


@dataclass
class AgentResponse:
    text: str
    metadata: Dict[str, Any] = field(default_factory=dict)


class AgentEvents:
    """Callbacks the UI implements to show progress. All are no-ops by default."""

    def on_text(self, delta: str) -> None:
        """Streamed model text."""

    def on_turn_end(self, turn: AssistantTurn) -> None:
        """A model response finished (text and any tool calls are complete)."""

    def on_tool_start(self, name: str, arguments: Dict[str, Any]) -> None:
        """A tool is about to run (after permission was granted)."""

    def on_tool_end(self, name: str, output: str, success: bool) -> None:
        """A tool finished, failed, or was denied."""

    def on_compact(self, tokens_before: int, tokens_after: int) -> None:
        """Older turns were summarized to free context."""


class Agent:
    """A tool-using conversational agent. One instance holds one conversation."""

    def __init__(
        self,
        client: Optional[ChatClient] = None,
        permissions: Optional[PermissionManager] = None,
        events: Optional[AgentEvents] = None,
        *,
        model: Optional[str] = None,
        provider: Optional[str] = None,
        max_turns: Optional[int] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        context_window: Optional[int] = None,
        compact_threshold: Optional[float] = None,
        tool_output_limit: Optional[int] = None,
        tool_names: Optional[Sequence[str]] = None,
        system_prompt: Optional[str] = None,
        cwd: Optional[Path] = None,
        session_id: Optional[str] = None,
        is_subagent: bool = False,
        stream: bool = True,
        persist: bool = False,
    ) -> None:
        """
        Args:
            client: Chat client; created from the environment when None
                (raises LLMError if no endpoint is configured)
            permissions: Permission gate; defaults to the configured mode with
                no approver (approval-required tools are denied)
            events: UI callbacks
            model: Model id used when creating the client
            provider: Provider name used when creating the client (see
                joshu.core.providers); defaults to the configured one
            tool_names: Restrict the agent to these tools (default: all enabled)
            system_prompt: Override the generated system prompt
            is_subagent: Sub-agents get the sub-agent prompt and no `task` tool
            stream: Stream text to events.on_text
            persist: Save the conversation after every request (see
                joshu.core.sessions) so it can be resumed
        """
        config = get_config_manager()

        self.client = client or create_chat_client(model, provider)
        self.permissions = permissions or PermissionManager(
            PermissionMode.from_string(config.get("permission_mode", "default"))
        )
        self.events = events or AgentEvents()
        self.max_turns = max_turns or config.get("agent_max_turns", 50)
        self.max_tokens = max_tokens or config.get("max_tokens", 4096)
        self.temperature = temperature if temperature is not None else 0.2
        self.context_window = context_window or config.get("context_window", 128000)
        self.compact_threshold = compact_threshold or config.get("compact_threshold", 0.8)
        self.tool_output_limit = tool_output_limit or config.get("tool_output_limit", 30000)
        self.cwd = cwd or Path.cwd()
        self.session_id = session_id or uuid.uuid4().hex[:12]
        self.created_at = datetime.now().isoformat(timespec="seconds")
        self.persist = persist and not is_subagent
        self.is_subagent = is_subagent
        self.stream = stream

        self._registry = load_builtin_tools()
        self._formatter = ToolExecutor(self._registry)
        self._tool_names = set(tool_names) if tool_names is not None else None
        self._local_tools: Dict[str, ToolSpec] = {}
        self.subagents: Dict[str, SubagentSpec] = {}
        if not is_subagent:
            self.subagents = discover_subagents(self.cwd)
            self._local_tools["task"] = self._make_task_tool()

        self._system_prompt_override = system_prompt
        self.messages: List[Dict[str, Any]] = [
            {"role": "system", "content": self._build_system_prompt()}
        ]
        self.usage: Dict[str, int] = {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "cached_tokens": 0,
        }
        self.cost = CostTracker()
        self._pricing: Dict[str, Any] = config.get("model_pricing") or {}
        self.diagnostics_enabled = bool(config.get("diagnostics_enabled", True))
        self._diagnostic_commands: Dict[str, str] = {
            str(ext).lower() if str(ext).startswith(".") else f".{str(ext).lower()}": str(cmd)
            for ext, cmd in (config.get("diagnostics") or {}).items()
        }
        self.tool_call_count = 0
        self.checkpoints = CheckpointStore()
        # Notes for the model about things that happened outside the loop (e.g. undo)
        self._pending_notes: List[str] = []

    # ------------------------------------------------------------------ public

    def set_mode(self, mode: PermissionMode) -> None:
        """Switch permission mode; the system prompt is updated to match."""
        self.permissions.mode = mode
        self.messages[0] = {"role": "system", "content": self._build_system_prompt()}

    def undo(self) -> Optional[Checkpoint]:
        """
        Revert the file edits made for the most recent request that edited files.

        The model is told about it at the start of the next request.

        Returns:
            The undone checkpoint (its `files` are the restored paths), or None
            when there is nothing to undo.
        """
        checkpoint = self.checkpoints.undo()
        if checkpoint is not None:
            paths = ", ".join(str(self._display_path(p)) for p in checkpoint.files)
            self._pending_notes.append(
                f"[Note: the user undid your file changes for the request "
                f"{checkpoint.prompt!r}. Restored: {paths}. Re-read files before editing them.]"
            )
        return checkpoint

    def reset(self) -> None:
        """
        Start a new conversation in a new session (keeps settings and session
        approvals). The previous conversation stays saved under its own id.
        """
        self.session_id = uuid.uuid4().hex[:12]
        self.created_at = datetime.now().isoformat(timespec="seconds")
        self.messages = [{"role": "system", "content": self._build_system_prompt()}]
        self.usage = {"prompt_tokens": 0, "completion_tokens": 0, "cached_tokens": 0}
        self.cost = CostTracker()
        self.checkpoints = CheckpointStore()
        self._pending_notes = []

    def tool_specs(self) -> List[ToolSpec]:
        """Tools offered to the model."""
        specs = [
            spec
            for spec in self._registry.get_available_tools(enabled_only=True)
            if self._tool_names is None or spec.name in self._tool_names
        ]
        specs.extend(
            spec
            for spec in self._local_tools.values()
            if self._tool_names is None or spec.name in self._tool_names
        )
        return specs

    def run(self, prompt: str, images: Sequence[Path] = ()) -> AgentResponse:
        """
        Run one user request to completion.

        KeyboardInterrupt propagates to the caller, but the history is left
        valid so the conversation can continue. With `persist`, the
        conversation is saved afterwards, also when interrupted.
        """
        from joshu.hooks.dispatcher import dispatch_after_agent

        try:
            response = self._run(prompt, images)
            dispatch_after_agent(self.session_id, prompt, response.text)
            return response
        finally:
            if self.persist and len(self.messages) > 1:
                self._save()

    def restore(self, session: Dict[str, Any]) -> None:
        """
        Continue a saved conversation (see joshu.core.sessions.load_session).

        The system prompt is rebuilt for the current environment.
        """
        self.session_id = session["id"]
        self.created_at = session.get("created_at", self.created_at)
        self.messages = [self.messages[0]] + list(session["messages"])
        for key, value in (session.get("usage") or {}).items():
            if key in self.usage:
                self.usage[key] = value
        self.cost = CostTracker.from_dict(session.get("cost"))

    def _save(self) -> None:
        from joshu.core.sessions import save_session

        try:
            save_session(self)
        except OSError as e:
            logger.warning(f"Could not save session {self.session_id}: {e}")

    def _run(self, prompt: str, images: Sequence[Path] = ()) -> AgentResponse:
        from joshu.hooks.dispatcher import dispatch_before_agent

        hook = dispatch_before_agent(self.session_id, prompt)
        if hook.should_block:
            message = (hook.response.message if hook.response else None) or "Blocked by hook."
            return AgentResponse(text=message, metadata={"blocked": True})

        self.checkpoints.begin(prompt)
        content = prompt
        if self._pending_notes:
            content = "\n".join(self._pending_notes) + "\n\n" + prompt
            self._pending_notes = []
        self.messages.append({"role": "user", "content": build_user_content(content, images)})
        tool_calls_before = self.tool_call_count

        for turn_number in range(1, self.max_turns + 1):
            self._maybe_compact()

            turn = self.client.complete(
                self.messages,
                tools=[spec.to_openai_format() for spec in self.tool_specs()] or None,
                max_tokens=self.max_tokens,
                temperature=self.temperature,
                on_text=self.events.on_text if self.stream else None,
            )
            self._add_usage(turn.usage)
            self.cost.add(
                request_cost(turn.usage, getattr(self.client, "model", ""), self._pricing)
            )
            self.messages.append(turn.to_message_dict())
            self.events.on_turn_end(turn)

            if not turn.tool_calls:
                return AgentResponse(
                    text=turn.content,
                    metadata=self._metadata(turn_number, tool_calls_before, turn.finish_reason),
                )

            self._run_tool_calls(turn.tool_calls)

        last_text = next(
            (m.get("content") for m in reversed(self.messages) if m.get("role") == "assistant"),
            "",
        )
        note = f"[Stopped after {self.max_turns} turns without finishing.]"
        return AgentResponse(
            text=f"{last_text}\n\n{note}".strip(),
            metadata={
                **self._metadata(self.max_turns, tool_calls_before, "max_turns"),
                "stopped": "max_turns",
            },
        )

    # ------------------------------------------------------------- tool calls

    def _run_tool_calls(self, calls: List[ToolCall]) -> None:
        answered = 0
        try:
            for call in calls:
                output = self._execute(call)
                self.messages.append({"role": "tool", "tool_call_id": call.id, "content": output})
                answered += 1
        except KeyboardInterrupt:
            # Every tool call needs a result or the next request is rejected
            for call in calls[answered:]:
                self.messages.append(
                    {"role": "tool", "tool_call_id": call.id, "content": "Interrupted by user."}
                )
            raise

    def _execute(self, call: ToolCall) -> str:
        from joshu.hooks.dispatcher import dispatch_after_tool, dispatch_before_tool

        self.tool_call_count += 1
        spec = self._find_tool(call.name)
        if spec is None:
            output = f"Error: unknown tool '{call.name}'."
            self.events.on_tool_end(call.name, output, False)
            return output

        try:
            arguments = call.parsed_arguments()
        except ValueError as e:
            output = f"Error: invalid arguments for '{call.name}': {e}"
            self.events.on_tool_end(call.name, output, False)
            return output

        hook = dispatch_before_tool(self.session_id, call.name, arguments)
        if hook.should_block:
            message = (hook.response.message if hook.response else None) or "no reason given"
            output = f"Blocked by hook: {message}"
            self.events.on_tool_end(call.name, output, False)
            return output
        if hook.response and hook.response.modified_data:
            modified = hook.response.modified_data.get("arguments")
            if isinstance(modified, dict):
                arguments = modified

        decision = self.permissions.check(call.name, arguments, spec.requires_approval)
        if not decision.allowed:
            output = f"Permission denied: {decision.reason}"
            self.events.on_tool_end(call.name, output, False)
            return output

        if call.name in EDIT_TOOLS:
            self._snapshot_target(arguments)

        self.events.on_tool_start(call.name, arguments)
        success, output = self._invoke(spec, arguments, self._formatter)
        if success and call.name in EDIT_TOOLS and self.diagnostics_enabled:
            output += self._diagnose(arguments)
        output = truncate_output(output, self.tool_output_limit)

        dispatch_after_tool(self.session_id, call.name, output, success)
        self.events.on_tool_end(call.name, output, success)
        return output

    def _diagnose(self, arguments: Dict[str, Any]) -> str:
        """Problems in the file an edit tool just wrote, formatted for the model."""
        from joshu.core.diagnostics import check_file
        from joshu.tools.filesystem_tools import resolve_path

        try:
            path = resolve_path(str(arguments.get("path", "")))
        except ValueError:
            return ""
        problems = check_file(path, self._diagnostic_commands)
        if not problems:
            return ""
        return (
            f"\n\nThe edit was applied, but {self._display_path(path)} now has problems. "
            f"Fix them before moving on:\n{problems}"
        )

    def _snapshot_target(self, arguments: Dict[str, Any]) -> None:
        """Record the file an edit tool is about to change, for undo."""
        from joshu.tools.filesystem_tools import resolve_path

        try:
            self.checkpoints.snapshot(resolve_path(str(arguments.get("path", ""))))
        except ValueError:
            pass  # outside the workspace: the tool itself will refuse

    def _display_path(self, path: Path) -> Path:
        try:
            return path.relative_to(self.cwd.resolve())
        except ValueError:
            return path

    def _find_tool(self, name: str) -> Optional[ToolSpec]:
        if self._tool_names is not None and name not in self._tool_names:
            return None
        spec = self._local_tools.get(name) or self._registry.get_tool(name)
        if spec is None or not spec.enabled:
            return None
        return spec

    @staticmethod
    def _invoke(
        spec: ToolSpec, arguments: Dict[str, Any], formatter: ToolExecutor
    ) -> tuple[bool, str]:
        try:
            value = spec.function(**arguments)
        except TypeError as e:
            return False, f"Error: invalid arguments for '{spec.name}': {e}"
        except KeyboardInterrupt:
            raise
        except Exception as e:
            logger.error(f"Tool {spec.name} raised: {e}", exc_info=True)
            return False, f"Error: {spec.name} failed: {e}"

        success = not (isinstance(value, dict) and value.get("success") is False)
        formatted = formatter.format_result_for_llm(
            {"success": True, "result": value, "error": None}
        )
        return success, formatted

    # ---------------------------------------------------------------- helpers

    def _build_system_prompt(self) -> str:
        if self._system_prompt_override is not None:
            return self._system_prompt_override
        return build_system_prompt(
            self.cwd,
            plan_mode=self.permissions.mode == PermissionMode.PLAN,
            subagent=self.is_subagent,
        )

    def _maybe_compact(self) -> None:
        tokens = estimate_tokens(self.messages)
        if tokens < self.context_window * self.compact_threshold:
            return
        compacted = compact_messages(self.messages, self.client)
        if compacted is not self.messages:
            self.messages = compacted
            self.events.on_compact(tokens, estimate_tokens(compacted))

    def _add_usage(self, usage: Dict[str, int]) -> None:
        for key in ("prompt_tokens", "completion_tokens", "cached_tokens"):
            self.usage[key] += usage.get(key, 0)

    def _metadata(self, turns: int, tool_calls_before: int, finish_reason: Any) -> Dict[str, Any]:
        return {
            "turns": turns,
            "tool_calls": self.tool_call_count - tool_calls_before,
            "finish_reason": finish_reason,
            "usage": dict(self.usage),
            "cost_usd": round(self.cost.total_usd, 6) if self.cost.known else None,
            "model": getattr(self.client, "model", None),
            "session_id": self.session_id,
        }

    def _make_task_tool(self) -> ToolSpec:
        def task(description: str, prompt: str, agent: Optional[str] = None) -> str:
            if agent:
                spec = self.subagents.get(agent)
                if spec is None:
                    known = ", ".join(sorted(self.subagents)) or "none defined"
                    return f"Error: unknown agent '{agent}' (available: {known})"
                sub_agent = self._make_defined_subagent(spec, description)
            else:
                sub_agent = self._make_subagent(
                    PermissionManager(PermissionMode.PLAN, approver=None),
                    description,
                    max_turns=SUBAGENT_MAX_TURNS,
                )
            response = sub_agent.run(prompt)
            self._add_usage(sub_agent.usage)
            self.cost.merge(sub_agent.cost)
            return response.text or "(the sub-agent returned no answer)"

        description = (
            "Delegate a focused task to a sub-agent. Without `agent`, a general sub-agent "
            "with read-only tools (read, list, glob, search, web search) handles it: use it "
            "for broad searches across many files, so their contents don't fill this "
            "conversation. The sub-agent sees only `prompt`, so make it self-contained; you "
            "get back its final answer."
        )
        properties: Dict[str, Any] = {
            "description": {
                "type": "string",
                "description": "Short (3-5 word) label for the task",
            },
            "prompt": {
                "type": "string",
                "description": "Complete instructions for the sub-agent",
            },
        }
        if self.subagents:
            listing = "\n".join(
                f"- {spec.name}: {spec.description}" for spec in self.subagents.values()
            )
            description += f"\n\nSpecialized agents (pass their name as `agent`):\n{listing}"
            properties["agent"] = {
                "type": "string",
                "enum": sorted(self.subagents),
                "description": "Name of a specialized agent to use (optional)",
            }

        return ToolSpec(
            name="task",
            description=description,
            parameters={
                "type": "object",
                "properties": properties,
                "required": ["description", "prompt"],
            },
            function=task,
            requires_approval=False,
        )

    def _make_subagent(
        self,
        permissions: PermissionManager,
        label: str,
        max_turns: int,
        client: Optional[ChatClient] = None,
        tool_names: Optional[Sequence[str]] = None,
        system_prompt: Optional[str] = None,
    ) -> "Agent":
        return Agent(
            client=client or self.client,
            permissions=permissions,
            events=_SubagentEvents(self.events, label),
            max_turns=min(self.max_turns, max_turns),
            max_tokens=self.max_tokens,
            temperature=self.temperature,
            context_window=self.context_window,
            tool_output_limit=self.tool_output_limit,
            tool_names=tool_names,
            system_prompt=system_prompt,
            cwd=self.cwd,
            session_id=f"{self.session_id}-sub",
            is_subagent=True,
            stream=False,
        )

    def _make_defined_subagent(self, spec: SubagentSpec, label: str) -> "Agent":
        """
        Sub-agent from a user definition.

        With a `tools` list it gets exactly those tools and shares this agent's
        permission gate (so edits and commands still need approval); without
        one it is read-only.
        """
        if spec.tools is None:
            permissions = PermissionManager(PermissionMode.PLAN, approver=None)
            tool_names = None
        else:
            permissions = self.permissions
            tool_names = spec.tools

        client = self.client
        if spec.model and spec.model != getattr(self.client, "model", None):
            client = create_chat_client(spec.model)

        return self._make_subagent(
            permissions,
            f"{spec.name}: {label}",
            max_turns=spec.max_turns or SUBAGENT_MAX_TURNS,
            client=client,
            tool_names=tool_names,
            system_prompt=build_subagent_prompt(spec.system_prompt, self.cwd),
        )


class _SubagentEvents(AgentEvents):
    """Shows a sub-agent's tool calls through the parent's UI, labelled."""

    def __init__(self, parent: AgentEvents, label: str) -> None:
        self.parent = parent
        self.label = label

    def on_tool_start(self, name: str, arguments: Dict[str, Any]) -> None:
        self.parent.on_tool_start(f"{self.label} › {name}", arguments)

    def on_tool_end(self, name: str, output: str, success: bool) -> None:
        self.parent.on_tool_end(f"{self.label} › {name}", output, success)


def truncate_output(text: str, limit: int) -> str:
    """Keep the head and tail of long tool output."""
    if limit <= 0 or len(text) <= limit:
        return text
    head = int(limit * 0.6)
    tail = limit - head
    omitted = len(text) - head - tail
    return f"{text[:head]}\n\n... [{omitted} characters omitted] ...\n\n{text[-tail:]}"
