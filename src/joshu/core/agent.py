"""
The agent loop.

Assemble context → call the model with tools → run each requested tool through
the permission gate and hooks → feed results back → repeat until the model
answers without calling a tool (or the turn limit is reached).
"""

from __future__ import annotations

import logging
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple, Union

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
    LLMError,
    ToolCall,
    create_chat_client,
)
from joshu.core.permissions import EDIT_TOOLS, PermissionManager, PermissionMode
from joshu.core.skills import (
    SKILL_TOOL_DESCRIPTION,
    Skill,
    discover_skills,
    model_skills,
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
# Read-only tools that may run at the same time when one turn requests several
PARALLEL_SAFE_TOOLS = {
    "read_file",
    "list_directory",
    "glob",
    "search_file_content",
    "web_search",
    "web_fetch",
    "bash_output",
    "skill",
    "task",
}
MAX_PARALLEL_TOOLS = 4
# Language-server errors shown to the model after an edit
MAX_LSP_ERRORS = 15

# Permission denials in one request: tell the model to stop using that tool
# (per tool), then end the request (all tools together)
DENIALS_WARN = 2
DENIALS_STOP = 6
# How many times stop hooks may send the agent back to work in one request
MAX_STOP_CONTINUES = 3
# Before finishing a request that changed files or ran commands, the agent is
# asked once to check its work against the request (the `self_review` setting)
SELF_REVIEW_NOTE = """[Self-check before you finish] Compare your work with the request before replying:
1. List each thing the request asked for (every file, function, call site, flag, removal) and confirm it is done.
2. Check the edge cases the request or the code's documentation mention (empty input, zero, negative numbers, boundaries, halves when rounding, input that should raise an error), with a quick check or the project's tests.
3. If the project has tests, run them.
Fix anything that is missing or wrong. If everything is done, reply with your final summary now."""
# A response cut off by the output limit: continue with a higher limit, this
# many times per request, up to this many output tokens
MAX_LENGTH_CONTINUES = 3
MAX_OUTPUT_TOKENS = 32768
LENGTH_NOTE = (
    "[Your last response was cut off at the output limit ({limit} tokens) before you "
    "finished. Continue from where you stopped. Keep your reasoning short and make the "
    "next tool call (or write the answer) now.]"
)


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

    def on_reasoning(self, delta: str) -> None:
        """Streamed reasoning, from models that show their thinking."""

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

    def on_parallel_start(self, count: int) -> None:
        """Several read-only tools are about to run at the same time."""

    # Set by interfaces that can put questions to the user (the ask_user tool
    # is only offered when this is true)
    can_ask_user = False

    def ask_user(self, questions: List[Any]) -> Optional[List[Any]]:
        """
        Ask the user `questions` (joshu.core.ask.Question): one answer per
        question, a list of chosen labels or typed text (None = skipped), or
        None when the user dismissed them.
        """
        return None


@dataclass
class _Prepared:
    """A tool call that passed its checks and is ready to run."""

    call: ToolCall
    spec: ToolSpec
    arguments: Dict[str, Any]


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
        max_budget_usd: Optional[float] = None,
        max_request_tokens: Optional[int] = None,
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
            max_budget_usd: Stop when the session has cost this much (0: no limit;
                default: the max_budget_usd setting)
            max_request_tokens: Stop a request that has used this many tokens
                (0: no limit; default: the max_request_tokens setting)
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
        self.max_tokens = max_tokens or config.get("max_tokens", 8192)
        self.max_budget_usd = float(
            max_budget_usd if max_budget_usd is not None else config.get("max_budget_usd", 0) or 0
        )
        self.max_request_tokens = int(
            max_request_tokens
            if max_request_tokens is not None
            else config.get("max_request_tokens", 0) or 0
        )
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
            if model_skills(self.skills):
                self._local_tools["skill"] = self._make_skill_tool()
            self._local_tools["install_skill"] = self._make_install_skill_tool()
            if getattr(self.events, "can_ask_user", False):
                self._local_tools["ask_user"] = self._make_ask_user_tool()
            self.auto_memory = bool(config.get("auto_memory", True))
            if self.auto_memory:
                self._local_tools["memory"] = self._make_memory_tool()
        self.self_review = bool(config.get("self_review", True)) and not is_subagent
        # Set when a request edits a file or runs a command (see _start)
        self._changed_this_request = False

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
        # session_start hooks have run for this session
        self._session_started = False
        # Permission denials per tool in the current request (denial guard)
        self._denials: Dict[str, int] = {}
        self._usage_at_start: Dict[str, int] = {}
        self.parallel_tools = bool(config.get("parallel_tools", True))
        # Sub-agents running in parallel add their usage from worker threads
        self._usage_lock = threading.Lock()

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
        self.end_session()
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
        from joshu.hooks.dispatcher import dispatch_before_agent, dispatch_session_start

        contexts = []
        if not self._session_started:
            self._session_started = True
            start = dispatch_session_start(
                self.session_id,
                {
                    "cwd": str(self.cwd),
                    "model": getattr(self.client, "model", None),
                    "resumed": len(self.messages) > 1,
                },
            )
            if start.context:
                contexts.append(start.context)

        hook = dispatch_before_agent(self.session_id, prompt)
        if hook.should_block:
            message = (hook.response.message if hook.response else None) or "Blocked by hook."
            return AgentResponse(text=message, metadata={"blocked": True})
        if hook.context:
            contexts.append(hook.context)

        self._request_count += 1
        self.checkpoints.begin(prompt, self._request_count)
        content = prompt
        notes = list(self._pending_notes)
        self._pending_notes = []
        if contexts:
            notes.append("[Context from hooks]\n" + "\n\n".join(contexts))
        if notes:
            content = "\n".join(notes) + "\n\n" + prompt
        self.messages.append({"role": "user", "content": build_user_content(content, images)})
        tool_calls_before = self.tool_call_count
        self._last_call, self._repeats = None, 0
        self._denials = {}
        self._usage_at_start = dict(self.usage)
        stop_continues = 0
        self._changed_this_request = False
        reviewed = False
        length_continues = 0
        max_tokens = self.max_tokens

        for turn_number in range(1, self.max_turns + 1):
            # Checked before each model call: after a tool round, never between
            # a call and its results
            limit = self._limit_reached()
            if limit is not None:
                self.messages.append({"role": "assistant", "content": limit})
                return AgentResponse(
                    text=limit,
                    metadata={
                        **self._metadata(turn_number - 1, tool_calls_before, "budget"),
                        "stopped": "budget",
                    },
                )
            self._maybe_compact()

            self.events.on_model_start()
            turn, max_tokens = self._complete(max_tokens)
            self._add_usage(turn.usage)
            self.cost.add(
                request_cost(turn.usage, getattr(self.client, "model", ""), self._pricing)
            )
            self.messages.append(turn.to_message_dict())
            self.events.on_turn_end(turn)

            if (
                turn.finish_reason == "length"
                and not turn.tool_calls
                and length_continues < MAX_LENGTH_CONTINUES
            ):
                # Cut off mid-thought (reasoning models spend output tokens on
                # thinking): this is not an answer. Raise the limit and go on.
                length_continues += 1
                logger.info(f"Response cut off at {max_tokens} output tokens; continuing")
                self.messages.append(
                    {"role": "user", "content": LENGTH_NOTE.format(limit=max_tokens)}
                )
                max_tokens = min(max_tokens * 2, MAX_OUTPUT_TOKENS)
                continue

            if not turn.tool_calls:
                reason = self._stop_hook_reason(prompt, turn.content, stop_continues)
                if reason is not None:
                    # A stop hook sent the agent back to work
                    stop_continues += 1
                    self.messages.append({"role": "user", "content": f"[Stop hook] {reason}"})
                    continue
                if self.self_review and self._changed_this_request and not reviewed:
                    reviewed = True
                    self.messages.append({"role": "user", "content": SELF_REVIEW_NOTE})
                    continue
                return AgentResponse(
                    text=turn.content,
                    metadata=self._metadata(turn_number, tool_calls_before, turn.finish_reason),
                )

            self._run_tool_calls(turn.tool_calls)
            if self.persist:
                # Also mid-request: a crash or a killed process keeps the work so far
                self._save()
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
        if self.parallel_tools and len(calls) > 1 and all(map(self._parallel_safe, calls)):
            self._run_parallel(calls)
            return
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

    def _parallel_safe(self, call: ToolCall) -> bool:
        """Read-only calls that never ask the user can run at the same time."""
        from joshu.core.secrets import sensitive_reason
        from joshu.core.tool_repair import repair_arguments

        if call.name not in PARALLEL_SAFE_TOOLS:
            return False
        try:
            arguments = repair_arguments(call.arguments)
        except ValueError:
            return False
        if sensitive_reason(call.name, arguments):
            return False
        if call.name == "task" and arguments.get("agent"):
            spec = self.subagents.get(str(arguments["agent"]))
            # Custom sub-agents with write tools may ask for approval: run them alone
            if spec is None or (spec.tools and not set(spec.tools) <= PARALLEL_SAFE_TOOLS):
                return False
        return True

    def _run_parallel(self, calls: List[ToolCall]) -> None:
        """Run read-only calls concurrently; results are shown and recorded in order."""
        from concurrent.futures import ThreadPoolExecutor

        prepared = [self._prepare(call) for call in calls]
        runnable = [p for p in prepared if not isinstance(p, str)]
        self.events.on_parallel_start(len(runnable))
        answered = 0
        try:
            with ThreadPoolExecutor(
                max_workers=min(MAX_PARALLEL_TOOLS, len(runnable) or 1)
            ) as pool:
                futures = {
                    id(p): pool.submit(self._invoke, p.spec, p.arguments, self._formatter)
                    for p in runnable
                }
                for call, item in zip(calls, prepared):
                    if isinstance(item, str):
                        output = item
                    else:
                        success, output = futures[id(item)].result()
                        self._start(item)
                        output = self._finish(item, success, output)
                    output = self._note_repeats(call, output)
                    self.messages.append(
                        {"role": "tool", "tool_call_id": call.id, "content": output}
                    )
                    answered += 1
        except KeyboardInterrupt:
            for call in calls[answered:]:
                self.messages.append(
                    {"role": "tool", "tool_call_id": call.id, "content": "Interrupted by user."}
                )
            raise

    def _complete(self, max_tokens: int) -> Tuple[AssistantTurn, int]:
        """
        One model turn. When a raised output limit is refused by the provider
        (some cap max_tokens), retry once with the configured limit.
        Returns the turn and the limit that was used.
        """
        request = dict(
            tools=self.request_tools() or None,
            temperature=self.temperature,
            on_text=self.events.on_text if self.stream else None,
            on_reasoning=self.events.on_reasoning if self.stream else None,
        )
        try:
            return self.client.complete(self.messages, max_tokens=max_tokens, **request), max_tokens
        except LLMError as e:
            if max_tokens <= self.max_tokens or e.unavailable:
                raise
            logger.info(f"Output limit {max_tokens} refused ({e}); using {self.max_tokens}")
            limit = self.max_tokens
            return self.client.complete(self.messages, max_tokens=limit, **request), limit

    def _stop_hook_reason(self, prompt: str, response: str, continues: int) -> Optional[str]:
        """Why a stop hook wants the agent to keep working, or None to finish."""
        from joshu.hooks.dispatcher import dispatch_stop

        if continues >= MAX_STOP_CONTINUES:
            return None
        hook = dispatch_stop(self.session_id, prompt, response, continues)
        if not hook.should_block:
            return None
        return (hook.response.message if hook.response else None) or (
            "A stop hook asked you to keep working before finishing."
        )

    def end_session(self) -> None:
        """Tell session_end hooks this conversation is over (if it started)."""
        from joshu.hooks.dispatcher import dispatch_session_end

        if self._session_started and not self.is_subagent:
            dispatch_session_end(self.session_id, {"cwd": str(self.cwd)})
            self._session_started = False

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
        prepared = self._prepare(call)
        if isinstance(prepared, str):
            return prepared
        self._start(prepared)
        success, output = self._invoke(prepared.spec, prepared.arguments, self._formatter)
        return self._finish(prepared, success, output)

    def _prepare(self, call: ToolCall) -> Union[str, "_Prepared"]:
        """
        Everything before running a tool: resolve it, check its arguments,
        hooks and permissions (asking the user if needed), and snapshot files
        for undo. Returns the tool result directly when the call can't run.
        """
        from joshu.core.tool_repair import repair_arguments, resolve_tool_name
        from joshu.hooks.dispatcher import dispatch_before_tool

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
        if call.name == "run_shell_command" and "install_skill" in self._local_tools:
            from joshu.core.skill_install import skills_add_part

            command = skills_add_part(str(arguments.get("command", "")))
            if command is not None:
                # `npx skills add` would install for every agent it knows; Joshu's
                # installer fetches the same thing and puts it where Joshu looks
                return _Prepared(call, self._local_tools["install_skill"], {"source": command})
        return _Prepared(call, spec, arguments)

    def _start(self, prepared: "_Prepared") -> None:
        call, arguments = prepared.call, prepared.arguments
        self.events.on_tool_start(call.name, arguments)
        # A deferred tool the model called directly stays offered from now on
        self._loaded_tools.add(call.name)
        if call.name in EDIT_TOOLS or call.name == "run_shell_command":
            self._changed_this_request = True
        if call.name == "run_shell_command" and arguments.get("background"):
            self._loaded_tools.update({"bash_output", "kill_bash"})

    def _finish(self, prepared: "_Prepared", success: bool, output: str) -> str:
        """Everything after running a tool: checks, masking, truncation, hooks, display."""
        from joshu.hooks.dispatcher import dispatch_after_tool

        call, arguments = prepared.call, prepared.arguments
        if success and call.name in EDIT_TOOLS and self.diagnostics_enabled:
            output += self._diagnose(arguments)
        from joshu.core.secrets import mask_secrets, masking_enabled

        if masking_enabled():
            output = mask_secrets(output)
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
            problems = self._language_server_errors(path)
        if not problems:
            return ""
        return (
            f"\n\nThe edit was applied, but {self._display_path(path)} now has problems. "
            f"Fix them before moving on:\n{problems}"
        )

    def _language_server_errors(self, path: Path) -> Optional[str]:
        """Errors a language server reports for the file, if one handles it."""
        from joshu.core.lsp import get_lsp_manager

        try:
            found = get_lsp_manager(self.cwd).diagnostics(path)
        except Exception as e:  # a language server problem must never break an edit
            logger.warning(f"Language server check failed: {e}")
            return None
        if not found:
            return None
        label = str(self._display_path(path))
        lines = [d.format(label) for d in found[:MAX_LSP_ERRORS]]
        if len(found) > MAX_LSP_ERRORS:
            lines.append(f"... and {len(found) - MAX_LSP_ERRORS} more")
        return "\n".join(lines)

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
        if "ask_user" in self._local_tools:
            from joshu.core.ask import ASK_PROMPT_RULE

            sections.append(ASK_PROMPT_RULE)
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
            if self._pre_compress_blocked("clear", tokens):
                return
            from joshu.core.context_editing import clear_old_tool_results

            cleared, count, freed = clear_old_tool_results(self.messages)
            if count:
                self.messages = cleared
                self.events.on_context_cleared(count, freed)
                tokens = estimate_tokens(self.messages)
        if tokens < self.context_window * self.compact_threshold:
            return
        if self._pre_compress_blocked("summarize", tokens):
            return
        compacted = compact_messages(self.messages, self.client)
        if compacted is not self.messages:
            self.messages = compacted
            self.events.on_compact(tokens, estimate_tokens(compacted))

    def _pre_compress_blocked(self, kind: str, tokens: int) -> bool:
        """Run pre_compress hooks; True when one blocks the clearing/summary."""
        from joshu.hooks.dispatcher import dispatch_pre_compress

        hook = dispatch_pre_compress(
            self.session_id, {"kind": kind, "tokens": tokens, "window": self.context_window}
        )
        return hook.should_block

    def _add_usage(self, usage: Dict[str, int]) -> None:
        with self._usage_lock:
            for key in ("prompt_tokens", "completion_tokens", "cached_tokens"):
                self.usage[key] += usage.get(key, 0)

    def _limit_reached(self) -> Optional[str]:
        """Why the spending limits stop the request now, or None."""
        if self.max_budget_usd > 0 and self.cost.total_usd >= self.max_budget_usd:
            return (
                f"[Stopped: the session's budget of ${self.max_budget_usd:.2f} is spent "
                f"(${self.cost.total_usd:.4f}). Raise max_budget_usd to continue.]"
            )
        if self.max_request_tokens > 0:
            used = sum(
                self.usage.get(key, 0) - self._usage_at_start.get(key, 0)
                for key in ("prompt_tokens", "completion_tokens")
            )
            if used >= self.max_request_tokens:
                return (
                    f"[Stopped: this request used {used:,} tokens, over the limit of "
                    f"{self.max_request_tokens:,} (max_request_tokens).]"
                )
        return None

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
            from joshu.hooks.dispatcher import dispatch_subagent_stop

            dispatch_subagent_stop(self.session_id, description, response.text)
            self._add_usage(sub_agent.usage)
            with self._usage_lock:
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

    def reload_skills(self) -> None:
        """Pick up skills installed or removed during the session."""
        if self.is_subagent:
            return
        self.skills = discover_skills(self.cwd)
        if model_skills(self.skills):
            self._local_tools["skill"] = self._make_skill_tool()
        else:
            self._local_tools.pop("skill", None)
        self.refresh_system_prompt()

    def _make_ask_user_tool(self) -> ToolSpec:
        from joshu.core.ask import (
            ASK_TOOL_DESCRIPTION,
            PARAMETERS,
            AskError,
            format_answers,
            parse_questions,
        )

        def ask_user(questions: Any) -> str:
            try:
                parsed = parse_questions(questions)
            except AskError as e:
                return f"Error: {e}"
            return format_answers(parsed, self.events.ask_user(parsed))

        return ToolSpec(
            name="ask_user",
            description=ASK_TOOL_DESCRIPTION,
            parameters=PARAMETERS,
            function=ask_user,
            requires_approval=False,
        )

    def _make_install_skill_tool(self) -> ToolSpec:
        def install_skill(
            source: str, skills: Optional[List[str]] = None, scope: str = "project"
        ) -> str:
            from joshu.core.skill_install import (
                AddRequest,
                SkillInstallError,
                describe,
                install_skills,
                parse_add_command,
            )

            try:
                request = parse_add_command(source)
            except SkillInstallError:
                request = AddRequest(source=source)
            request.skills.extend(skills or [])
            request.global_ = request.global_ or scope == "user"
            try:
                result = install_skills(request, cwd=self.cwd)
            except SkillInstallError as e:
                return f"Error: {e}"
            if result.installed:
                self.reload_skills()
            return describe(result, request)

        return ToolSpec(
            name="install_skill",
            description=(
                "Download and install agent skills when the user asks to add one. Accepts what "
                "skill pages give: `npx skills add owner/repo --skill name`, a GitHub owner/repo "
                "or URL. Installed skills become available right away."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "source": {
                        "type": "string",
                        "description": "owner/repo, a URL, or the full `npx skills add ...` command",
                    },
                    "skills": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Skill names to install from the source",
                    },
                    "scope": {
                        "type": "string",
                        "enum": ["project", "user"],
                        "description": "project (.agents/skills) or user (~/.joshu/skills)",
                    },
                },
                "required": ["source"],
            },
            function=install_skill,
            requires_approval=True,
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
                    "name": {"type": "string", "enum": sorted(model_skills(self.skills))},
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
