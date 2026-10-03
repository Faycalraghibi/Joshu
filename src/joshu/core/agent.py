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
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from joshu.core.compaction import compact_messages, estimate_tokens
from joshu.core.config import get_config_manager
from joshu.core.llm_client import (
    AssistantTurn,
    ChatClient,
    ToolCall,
    create_chat_client,
)
from joshu.core.permissions import PermissionManager, PermissionMode
from joshu.core.system_prompt import build_system_prompt
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
    ) -> None:
        """
        Args:
            client: Chat client; created from the environment when None
                (raises LLMError if no endpoint is configured)
            permissions: Permission gate; defaults to the configured mode with
                no approver (approval-required tools are denied)
            events: UI callbacks
            model: Model id used when creating the client
            tool_names: Restrict the agent to these tools (default: all enabled)
            system_prompt: Override the generated system prompt
            is_subagent: Sub-agents get the sub-agent prompt and no `task` tool
            stream: Stream text to events.on_text
        """
        config = get_config_manager()

        self.client = client or create_chat_client(model or config.get("model"))
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
        self.is_subagent = is_subagent
        self.stream = stream

        self._registry = load_builtin_tools()
        self._formatter = ToolExecutor(self._registry)
        self._tool_names = set(tool_names) if tool_names is not None else None
        self._local_tools: Dict[str, ToolSpec] = {}
        if not is_subagent:
            self._local_tools["task"] = self._make_task_tool()

        self._system_prompt_override = system_prompt
        self.messages: List[Dict[str, Any]] = [
            {"role": "system", "content": self._build_system_prompt()}
        ]
        self.usage: Dict[str, int] = {"prompt_tokens": 0, "completion_tokens": 0}
        self.tool_call_count = 0

    # ------------------------------------------------------------------ public

    def set_mode(self, mode: PermissionMode) -> None:
        """Switch permission mode; the system prompt is updated to match."""
        self.permissions.mode = mode
        self.messages[0] = {"role": "system", "content": self._build_system_prompt()}

    def reset(self) -> None:
        """Start a new conversation (keeps settings and session approvals)."""
        self.messages = [{"role": "system", "content": self._build_system_prompt()}]

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

    def run(self, prompt: str) -> AgentResponse:
        """
        Run one user request to completion.

        KeyboardInterrupt propagates to the caller, but the history is left
        valid so the conversation can continue.
        """
        from joshu.hooks.dispatcher import dispatch_before_agent

        hook = dispatch_before_agent(self.session_id, prompt)
        if hook.should_block:
            message = (hook.response.message if hook.response else None) or "Blocked by hook."
            return AgentResponse(text=message, metadata={"blocked": True})

        self.messages.append({"role": "user", "content": prompt})
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

        self.events.on_tool_start(call.name, arguments)
        success, output = self._invoke(spec, arguments, self._formatter)
        output = truncate_output(output, self.tool_output_limit)

        dispatch_after_tool(self.session_id, call.name, output, success)
        self.events.on_tool_end(call.name, output, success)
        return output

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
        for key in ("prompt_tokens", "completion_tokens"):
            self.usage[key] += usage.get(key, 0)

    def _metadata(self, turns: int, tool_calls_before: int, finish_reason: Any) -> Dict[str, Any]:
        return {
            "turns": turns,
            "tool_calls": self.tool_call_count - tool_calls_before,
            "finish_reason": finish_reason,
            "usage": dict(self.usage),
            "model": getattr(self.client, "model", None),
            "session_id": self.session_id,
        }

    def _make_task_tool(self) -> ToolSpec:
        def task(description: str, prompt: str) -> str:
            sub_agent = Agent(
                client=self.client,
                permissions=PermissionManager(PermissionMode.PLAN, approver=None),
                events=_SubagentEvents(self.events, description),
                max_turns=min(self.max_turns, SUBAGENT_MAX_TURNS),
                max_tokens=self.max_tokens,
                temperature=self.temperature,
                context_window=self.context_window,
                tool_output_limit=self.tool_output_limit,
                cwd=self.cwd,
                session_id=f"{self.session_id}-sub",
                is_subagent=True,
                stream=False,
            )
            response = sub_agent.run(prompt)
            self._add_usage(sub_agent.usage)
            return response.text or "(the sub-agent returned no answer)"

        return ToolSpec(
            name="task",
            description=(
                "Delegate a focused research task to a sub-agent with read-only tools "
                "(read, list, glob, search, web search). Use it for broad searches across "
                "many files, so their contents don't fill this conversation. The sub-agent "
                "sees only `prompt`, so make it self-contained; you get back its final answer."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "description": {
                        "type": "string",
                        "description": "Short (3-5 word) label for the task",
                    },
                    "prompt": {
                        "type": "string",
                        "description": "Complete instructions for the sub-agent",
                    },
                },
                "required": ["description", "prompt"],
            },
            function=task,
            requires_approval=False,
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
