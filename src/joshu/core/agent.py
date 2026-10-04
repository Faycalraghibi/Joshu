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
from typing import Any, Dict, List, Optional, Sequence, Set

from joshu.core.auto_memory import TYPES as MEMORY_TYPES
from joshu.core.auto_memory import memory_prompt, run_memory_tool
from joshu.core.checkpoints import Checkpoint, CheckpointStore
from joshu.core.compaction import SUMMARY_PREFIX, compact_messages, estimate_tokens
from joshu.core.config import get_config_manager
from joshu.core.costs import CostTracker, request_cost
from joshu.core.images import build_user_content, message_text
from joshu.core.llm_client import (
    AssistantTurn,
    ChatClient,
    ToolCall,
    create_chat_client,
)
from joshu.core.permissions import EDIT_TOOLS, PermissionManager, PermissionMode
from joshu.core.skills import (
    SKILL_TOOL_DESCRIPTION,
    Skill,
    discover_skills,
    run_skill_tool,
    skills_prompt,
)
from joshu.core.subagents import SubagentSpec, discover_subagents
from joshu.core.system_prompt import build_subagent_prompt, build_system_prompt
from joshu.core.tool_executor import ToolExecutor
from joshu.core.tool_registry import ToolSpec, load_builtin_tools

logger = logging.getLogger(__name__)

SUBAGENT_MAX_TURNS = 25
# Identical calls with identical results in a row: warn the model, then stop
LOOP_WARN = 3
LOOP_STOP = 5
# Permission denials in one request: tell the model to stop using that tool
# (per tool), then end the request (all tools together)
DENIALS_WARN = 2
DENIALS_STOP = 6


@dataclass
class AgentResponse:
    text: str
    metadata: Dict[str, Any] = field(default_factory=dict)


class AgentEvents:
    """Callbacks the UI implements to show progress. All are no-ops by default."""

    def on_model_start(self) -> None:
        """A request to the model is about to be sent (show a working indicator)."""

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

    def on_context_cleared(self, items: int, tokens_freed: int) -> None:
        """Old tool results were replaced by short notes to free context."""


@dataclass
class Rewind:
    """What `Agent.rewind` removed."""

    prompts: List[str]
    files: List[Path]


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
        self.context_window = (
            context_window
            or getattr(self.client, "context_window", None)
            or config.get("context_window", 128000)
        )
        self.compact_threshold = compact_threshold or config.get("compact_threshold", 0.8)
        self.tool_output_limit = tool_output_limit or config.get("tool_output_limit", 16000)
        # Estimated tokens at which old tool results get cleared (0: never): the
        # setting, but never more than half the context window
        clear_at = int(config.get("clear_tool_results_at", 60000) or 0)
        self.clear_tool_results_at = min(clear_at, self.context_window // 2) if clear_at else 0
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
        # Deferred (MCP) tools whose definitions the model has loaded
        self._loaded_tools: Set[str] = set()
        self._defer_mode = config.get("defer_mcp_tools", "auto")
        self.subagents: Dict[str, SubagentSpec] = {}
        self.skills: Dict[str, Skill] = {}
        self.auto_memory = False
        if not is_subagent:
            self.subagents = discover_subagents(self.cwd)
            self._local_tools["task"] = self._make_task_tool()
            self.skills = discover_skills(self.cwd)
            if self.skills:
                self._local_tools["skill"] = self._make_skill_tool()
            self.auto_memory = bool(config.get("auto_memory", True))
            if self.auto_memory:
                self._local_tools["memory"] = self._make_memory_tool()

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
        # Identical consecutive tool calls with identical results (loop detection)
        self._last_call: Optional[tuple] = None
        self._repeats = 0
        # Requests handled in this conversation; checkpoints are tagged with it
        self._request_count = 0
        # Permission denials per tool in the current request (denial guard)
        self._denials: Dict[str, int] = {}
        self._usage_at_start: Dict[str, int] = {}

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

    def requests(self) -> List[str]:
        """The user's requests in the current history, oldest first."""
        return [message_text(self.messages[i].get("content")) for i in self._request_indices()]

    def rewind(self, count: int = 1) -> Optional[Rewind]:
        """
        Remove the last `count` requests (and everything after them) from the
        conversation and restore the files the agent edited while handling them.

        Requests summarized away by compaction can't be rewound. Changes made
        by shell commands aren't tracked and stay.

        Returns:
            What was removed, or None when there is nothing to rewind.
        """
        indices = self._request_indices()
        if count < 1 or not indices:
            return None
        count = min(count, len(indices))
        cut = indices[-count]
        removed = [
            message_text(m.get("content")) for m in self.messages[cut:] if self._is_request(m)
        ]
        self.messages = self.messages[:cut]
        first_removed = self._request_count - count + 1
        undone = self.checkpoints.undo_since(first_removed)
        self._request_count = first_removed - 1
        self._pending_notes = []
        files = sorted({p for c in undone for p in c.files}, key=str)
        if self.persist:
            self._save()
        return Rewind(prompts=removed, files=files)

    def compact(self, focus: str = "") -> Optional[tuple]:
        """
        Summarize the conversation now, keeping the last request verbatim.

        Returns:
            (tokens before, tokens after), or None when there was nothing to compact.
        """
        before = estimate_tokens(self.messages)
        compacted = compact_messages(self.messages, self.client, keep_recent=1, focus=focus)
        if compacted is self.messages:
            return None
        self.messages = compacted
        after = estimate_tokens(compacted)
        self.events.on_compact(before, after)
        if self.persist:
            self._save()
        return before, after

    def _request_indices(self) -> List[int]:
        """Positions of the user's requests that are still verbatim in the history."""
        return [i for i, m in enumerate(self.messages) if i > 0 and self._is_request(m)]

    @staticmethod
    def _is_request(message: Dict[str, Any]) -> bool:
        if message.get("role") != "user":
            return False
        return not message_text(message.get("content")).startswith(SUMMARY_PREFIX)

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
        self._request_count = 0

    def tool_specs(self) -> List[ToolSpec]:
        """Tools offered to the model (deferred tools only once loaded)."""
        specs = self._all_tool_specs()
        deferred = self.deferred_tools(specs)
        if not deferred:
            return specs
        hidden = {spec.name for spec in deferred}
        return [spec for spec in specs if spec.name not in hidden] + [self._load_tools_spec()]

    def request_tools(self) -> List[Dict[str, Any]]:
        """The tool definitions sent with a request (trimmed, see joshu.core.tool_schema)."""
        from joshu.core.tool_schema import lean_definition

        return [lean_definition(spec.to_openai_format()) for spec in self.tool_specs()]

    def deferred_tools(self, specs: Optional[List[ToolSpec]] = None) -> List[ToolSpec]:
        """Tools whose definitions aren't sent until the model loads them."""
        from joshu.core.deferred_tools import DEFERRED_BUILTINS, server_of, should_defer

        if self.is_subagent:
            return []
        specs = specs if specs is not None else self._all_tool_specs()
        mcp = [spec for spec in specs if server_of(spec)]
        deferred = [spec for spec in specs if spec.name in DEFERRED_BUILTINS]
        if should_defer(self._defer_mode, mcp):
            deferred += mcp
        return [spec for spec in deferred if spec.name not in self._loaded_tools]

    def _all_tool_specs(self) -> List[ToolSpec]:
        specs = [
            spec
            for spec in self._registry.get_available_tools(enabled_only=True)
            if (self._tool_names is None or spec.name in self._tool_names)
            # The `memory` tool replaces the older save_memory when auto memory is on
            and not (spec.name == "save_memory" and "memory" in self._local_tools)
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
        self._request_count = len(self._request_indices())

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

        self._request_count += 1
        self.checkpoints.begin(prompt, self._request_count)
        content = prompt
        if self._pending_notes:
            content = "\n".join(self._pending_notes) + "\n\n" + prompt
            self._pending_notes = []
        self.messages.append({"role": "user", "content": build_user_content(content, images)})
        tool_calls_before = self.tool_call_count
        self._last_call, self._repeats = None, 0
        self._denials = {}
        self._usage_at_start = dict(self.usage)

        for turn_number in range(1, self.max_turns + 1):
            self._maybe_compact()

            self.events.on_model_start()
            turn = self.client.complete(
                self.messages,
                tools=self.request_tools() or None,
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
            if sum(self._denials.values()) >= DENIALS_STOP:
                note = (
                    "[Stopped: tool calls kept being denied. Allow them (e.g. /permissions) "
                    "or rephrase the request.]"
                )
                return AgentResponse(
                    text=f"{turn.content}\n\n{note}".strip(),
                    metadata={
                        **self._metadata(turn_number, tool_calls_before, "denied"),
                        "stopped": "denied",
                    },
                )
            if self._repeats >= LOOP_STOP:
                note = (
                    f"[Stopped: the same tool call returned the same result {self._repeats} "
                    "times in a row.]"
                )
                return AgentResponse(
                    text=f"{turn.content}\n\n{note}".strip(),
                    metadata={
                        **self._metadata(turn_number, tool_calls_before, "loop"),
                        "stopped": "loop",
                    },
                )

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
                output = self._note_repeats(call, self._execute(call))
                self.messages.append({"role": "tool", "tool_call_id": call.id, "content": output})
                answered += 1
        except KeyboardInterrupt:
            # Every tool call needs a result or the next request is rejected
            for call in calls[answered:]:
                self.messages.append(
                    {"role": "tool", "tool_call_id": call.id, "content": "Interrupted by user."}
                )
            raise

    def _note_repeats(self, call: ToolCall, output: str) -> str:
        """Warn the model when it repeats a call that keeps giving the same result."""
        signature = (call.name, " ".join((call.arguments or "").split()), output)
        if signature == self._last_call:
            self._repeats += 1
        else:
            self._last_call, self._repeats = signature, 1
        if self._repeats >= LOOP_WARN:
            output += (
                f"\n\n[This exact call has now returned the same result {self._repeats} times "
                "in a row. Repeating it won't help: change the arguments, try another "
                "approach, or explain what is blocking you.]"
            )
        return output

    def _execute(self, call: ToolCall) -> str:
        from joshu.core.tool_repair import repair_arguments, resolve_tool_name
        from joshu.hooks.dispatcher import dispatch_after_tool, dispatch_before_tool

        self.tool_call_count += 1
        spec = self._find_tool(call.name)
        if spec is None:
            available = [s.name for s in self.tool_specs()]
            resolved = resolve_tool_name(call.name, available)
            spec = self._find_tool(resolved) if resolved else None
            if spec is None:
                output = (
                    f"Error: unknown tool '{call.name}'. Available tools: "
                    f"{', '.join(sorted(available))}."
                )
                self.events.on_tool_end(call.name, output, False)
                return output
            logger.debug(f"Tool name '{call.name}' resolved to '{spec.name}'")
            call = ToolCall(id=call.id, name=spec.name, arguments=call.arguments)

        try:
            arguments = repair_arguments(call.arguments)
        except ValueError as e:
            output = (
                f"Error: invalid arguments for '{call.name}': {e}. Send a JSON object "
                f"with these fields: {_parameter_summary(spec)}."
            )
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
            self._denials[call.name] = self._denials.get(call.name, 0) + 1
            if self._denials[call.name] >= DENIALS_WARN:
                output += (
                    f" This is denial number {self._denials[call.name]} for {call.name} in this "
                    f"request: don't call {call.name} again. Continue without it, or finish "
                    "and tell the user what you need them to allow."
                )
            self.events.on_tool_end(call.name, output, False)
            return output

        if call.name in EDIT_TOOLS:
            self._snapshot_target(arguments)

        self.events.on_tool_start(call.name, arguments)
        # A deferred tool the model called directly stays offered from now on
        self._loaded_tools.add(call.name)
        if call.name == "run_shell_command" and arguments.get("background"):
            self._loaded_tools.update({"bash_output", "kill_bash"})
        success, output = self._invoke(spec, arguments, self._formatter)
        if success and call.name in EDIT_TOOLS and self.diagnostics_enabled:
            output += self._diagnose(arguments)
        # read_file limits itself to whole lines; don't cut its result in the middle
        limit = self.tool_output_limit
        if call.name == "read_file":
            from joshu.tools.filesystem_tools import READ_MAX_CHARS

            limit = max(limit, READ_MAX_CHARS + READ_MAX_CHARS // 2)
        output = truncate_output(output, limit)

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
        if name == "load_tools":
            return self._load_tools_spec() if self.deferred_tools() else None
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
            return False, (
                f"Error: invalid arguments for '{spec.name}': {e}. "
                f"Parameters: {_parameter_summary(spec)}."
            )
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

    def refresh_system_prompt(self) -> None:
        """Rebuild the system prompt (after settings such as the output style change)."""
        if self.messages and self.messages[0].get("role") == "system":
            self.messages[0] = {"role": "system", "content": self._build_system_prompt()}

    def _build_system_prompt(self) -> str:
        if self._system_prompt_override is not None:
            return self._system_prompt_override
        sections = []
        from joshu.core.output_styles import style_instructions

        style = style_instructions(get_config_manager().get("output_style"), self.cwd)
        if style and not self.is_subagent:
            sections.append(style)
        if self.skills:
            sections.append(skills_prompt(self.skills))
        if self.auto_memory:
            sections.append(memory_prompt(self.cwd))
        deferred = self.deferred_tools()
        if deferred:
            from joshu.core.deferred_tools import index_prompt

            sections.append(index_prompt(deferred))
        return build_system_prompt(
            self.cwd,
            plan_mode=self.permissions.mode == PermissionMode.PLAN,
            subagent=self.is_subagent,
            sections=sections,
        )

    def _maybe_compact(self) -> None:
        tokens = estimate_tokens(self.messages)
        # Cheapest first: clear old tool results; summarize only if still too big
        if self.clear_tool_results_at and tokens >= self.clear_tool_results_at:
            from joshu.core.context_editing import clear_old_tool_results

            cleared, count, freed = clear_old_tool_results(self.messages)
            if count:
                self.messages = cleared
                self.events.on_context_cleared(count, freed)
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
            "request_usage": {
                key: self.usage.get(key, 0) - self._usage_at_start.get(key, 0)
                for key in ("prompt_tokens", "completion_tokens", "cached_tokens")
            },
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
            "Delegate a focused task to a read-only sub-agent (e.g. a broad search across "
            "many files) and get back its answer. It sees only `prompt`: make it "
            "self-contained."
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

    def _load_tools_spec(self) -> ToolSpec:
        from joshu.core.deferred_tools import (
            LOAD_TOOLS,
            LOAD_TOOLS_DESCRIPTION,
            LOAD_TOOLS_PARAMETERS,
            match,
        )

        def load_tools(names: Optional[List[str]] = None, query: str = "") -> Dict[str, Any]:
            deferred = self.deferred_tools()
            if isinstance(names, str):
                names = [names]
            found = match(deferred, names or [], query or "")
            if not found:
                return {
                    "success": False,
                    "error": "No matching tools. Not yet loaded: "
                    + ", ".join(sorted(s.name for s in deferred)),
                }
            self._loaded_tools.update(spec.name for spec in found)
            return {
                "success": True,
                "loaded": [spec.name for spec in found],
                "message": "These tools are now available; call them directly.",
            }

        return ToolSpec(
            name=LOAD_TOOLS,
            description=LOAD_TOOLS_DESCRIPTION,
            parameters=LOAD_TOOLS_PARAMETERS,
            function=load_tools,
            requires_approval=False,
        )

    def _make_skill_tool(self) -> ToolSpec:
        def skill(name: str, file: Optional[str] = None) -> str:
            return run_skill_tool(self.skills, name, file)

        return ToolSpec(
            name="skill",
            description=SKILL_TOOL_DESCRIPTION,
            parameters={
                "type": "object",
                "properties": {
                    "name": {"type": "string", "enum": sorted(self.skills)},
                    "file": {
                        "type": "string",
                        "description": "A supporting file of the skill (relative path)",
                    },
                },
                "required": ["name"],
            },
            function=skill,
            requires_approval=False,
        )

    def _make_memory_tool(self) -> ToolSpec:
        def memory(
            action: str,
            name: str = "",
            description: str = "",
            content: str = "",
            type: str = "project",
            scope: str = "project",
        ) -> Dict[str, Any]:
            return run_memory_tool(action, name, description, content, type, scope, self.cwd)

        return ToolSpec(
            name="memory",
            description=(
                "Save, read or delete your notes for future sessions (see Memory in the "
                "system prompt). save with an existing name replaces that memory."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "action": {"type": "string", "enum": ["save", "read", "delete"]},
                    "name": {
                        "type": "string",
                        "description": "Short kebab-case slug, e.g. test-command",
                    },
                    "description": {
                        "type": "string",
                        "description": "One line for the index (save only)",
                    },
                    "content": {"type": "string", "description": "The memory (save only)"},
                    "type": {"type": "string", "enum": list(MEMORY_TYPES)},
                    "scope": {
                        "type": "string",
                        "enum": ["project", "user"],
                        "description": "project (default): this repository; user: every project",
                    },
                },
                "required": ["action", "name"],
            },
            function=memory,
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

    def on_model_start(self) -> None:
        self.parent.on_model_start()

    def on_tool_start(self, name: str, arguments: Dict[str, Any]) -> None:
        self.parent.on_tool_start(f"{self.label} › {name}", arguments)

    def on_tool_end(self, name: str, output: str, success: bool) -> None:
        self.parent.on_tool_end(f"{self.label} › {name}", output, success)


def _parameter_summary(spec: ToolSpec) -> str:
    """`path (required), limit` from a tool's JSON schema, for error messages."""
    schema = spec.parameters or {}
    properties = schema.get("properties") or {}
    required = set(schema.get("required") or [])
    if not properties:
        return "none"
    return ", ".join(f"{name} (required)" if name in required else name for name in properties)


def truncate_output(text: str, limit: int) -> str:
    """Keep the head and tail of long tool output."""
    if limit <= 0 or len(text) <= limit:
        return text
    head = int(limit * 0.6)
    tail = limit - head
    omitted = len(text) - head - tail
    return f"{text[:head]}\n\n... [{omitted} characters omitted] ...\n\n{text[-tail:]}"
