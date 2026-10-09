"""
Using Joshu from Python.

    from joshu import Session, run

    result = run("Fix the failing test in calc.py", permission_mode="accept_edits")
    print(result.text, result.usage)

    with Session(cwd="path/to/project", on_event=print) as session:
        session.send("Read the README and summarize it")
        session.send("Now list the open TODOs")       # same conversation

    with Session() as session:
        for event in session.stream("Explain src/app.py"):
            if event["type"] == "tool_use":
                print("using", event["name"])

Events are plain dicts (also what `joshu run --output-format stream-json`
prints, one per line):

    {"type": "text", "text": "..."}                       streamed text (stream_text=True)
    {"type": "assistant", "text": "...", "tool_calls": [{"name": ..., "input": {...}}]}
    {"type": "tool_use", "name": "read_file", "input": {...}}
    {"type": "tool_result", "name": "read_file", "output": "...", "success": true}
    {"type": "compact", "tokens_before": n, "tokens_after": n}
    {"type": "result", "text": "...", "session_id": ..., "turns": n, "tool_calls": n,
     "usage": {...}, "cost_usd": ..., "model": ..., "stopped": null}

Tools that need approval are decided by `permission_mode` and, when given,
`can_use_tool(name, input) -> bool`; without it they are denied, as in
`joshu run --print`. File tools work inside `cwd` (one workspace per process).
"""

from __future__ import annotations

import queue
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, Iterator, List, Optional, Sequence, Union

Event = Dict[str, Any]
EventHandler = Callable[[Event], None]
ToolFilter = Callable[[str, Dict[str, Any]], bool]


@dataclass
class Result:
    """The outcome of one request."""

    text: str
    session_id: str
    turns: int = 0
    tool_calls: int = 0
    usage: Dict[str, int] = field(default_factory=dict)
    cost_usd: Optional[float] = None
    model: Optional[str] = None
    stopped: Optional[str] = None  # "max_turns", "loop", "denied", "budget" when cut short
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_event(self) -> Event:
        return {
            "type": "result",
            "text": self.text,
            "session_id": self.session_id,
            "turns": self.turns,
            "tool_calls": self.tool_calls,
            "usage": self.usage,
            "cost_usd": self.cost_usd,
            "model": self.model,
            "stopped": self.stopped,
        }


def _events_class():
    from joshu.core.agent import AgentEvents

    class _Events(AgentEvents):
        """Turns agent callbacks into event dicts."""

        def __init__(self, emit: EventHandler, stream_text: bool) -> None:
            self.emit = emit
            self.stream_text = stream_text

        def on_text(self, delta: str) -> None:
            if self.stream_text and delta:
                self.emit({"type": "text", "text": delta})

        def on_turn_end(self, turn) -> None:
            self.emit(
                {
                    "type": "assistant",
                    "text": turn.content or "",
                    "tool_calls": [
                        {"name": call.name, "input": _arguments(call.arguments)}
                        for call in turn.tool_calls
                    ],
                }
            )

        def on_tool_start(self, name: str, arguments: Dict[str, Any]) -> None:
            self.emit({"type": "tool_use", "name": name, "input": arguments})

        def on_tool_end(self, name: str, output: str, success: bool) -> None:
            self.emit({"type": "tool_result", "name": name, "output": output, "success": success})

        def on_compact(self, tokens_before: int, tokens_after: int) -> None:
            self.emit(
                {"type": "compact", "tokens_before": tokens_before, "tokens_after": tokens_after}
            )

    return _Events


def _arguments(raw: str) -> Dict[str, Any]:
    from joshu.core.tool_repair import repair_arguments

    try:
        return repair_arguments(raw)
    except ValueError:
        return {"_raw": raw}


class Session:
    """A conversation with the agent that keeps its history between `send` calls."""

    def __init__(
        self,
        *,
        model: Optional[str] = None,
        provider: Optional[str] = None,
        permission_mode: str = "default",
        cwd: Union[str, Path, None] = None,
        tools: Optional[Sequence[str]] = None,
        can_use_tool: Optional[ToolFilter] = None,
        ask_user: Optional[Callable[[List[Any]], Optional[List[Any]]]] = None,
        system_prompt: Optional[str] = None,
        append_system_prompt: Optional[str] = None,
        on_event: Optional[EventHandler] = None,
        stream_text: bool = False,
        load_mcp: bool = False,
        persist: bool = False,
        resume: Optional[str] = None,
        max_turns: Optional[int] = None,
        max_budget_usd: Optional[float] = None,
        max_request_tokens: Optional[int] = None,
        client: Any = None,
    ) -> None:
        """
        Args:
            model, provider: Override the configured model / provider
            permission_mode: default, accept_edits, auto, plan or bypass
            cwd: Project directory (file tools work inside it)
            tools: Only offer these tools (default: all)
            can_use_tool: Decides calls that need approval (default: deny them)
            ask_user: Answers the agent's questions: gets a list of
                joshu.core.ask.Question, returns one answer per question (a list
                of chosen labels, or typed text; None to skip), or None. Without
                it the agent isn't offered the ask_user tool
            system_prompt: Replace the generated system prompt
            append_system_prompt: Add this at the end of the system prompt
            on_event: Receives every event as it happens
            stream_text: Also emit {"type": "text"} deltas while the model writes
            load_mcp: Start the configured MCP servers and offer their tools
            persist: Save the conversation like the CLI does (resumable)
            resume: Continue a saved session: its id, or "last" for the latest here
            max_budget_usd: Stop when the session has cost this much (0: no limit)
            max_request_tokens: Stop a request after this many tokens (0: no limit)
            client: A ready chat client (anything with `complete`), instead of
                building one from model / provider

        Raises:
            joshu.core.llm_client.LLMError: no usable model / provider configured
        """
        from joshu.core.agent import Agent
        from joshu.core.config import get_config_manager
        from joshu.core.permissions import (
            ApprovalChoice,
            PermissionManager,
            PermissionMode,
        )
        from joshu.hooks import configure_hooks_from_settings
        from joshu.tools import filesystem_tools

        self.cwd = Path(cwd).resolve() if cwd else Path.cwd().resolve()
        filesystem_tools.set_workspace_root(self.cwd)
        config = get_config_manager()
        configure_hooks_from_settings(config.get("hooks") or {})
        if load_mcp:
            from joshu.mcp.startup import load_mcp_tools

            load_mcp_tools()

        self._handlers: List[EventHandler] = [on_event] if on_event else []
        approver = None
        if can_use_tool is not None:

            def approver(request):
                allowed = can_use_tool(request.tool_name, dict(request.arguments))
                return ApprovalChoice.YES if allowed else ApprovalChoice.NO

        events = _events_class()(self._emit, stream_text)
        if ask_user is not None:
            events.can_ask_user = True
            events.ask_user = ask_user
        self.agent = Agent(
            client=client,
            model=model,
            provider=provider,
            permissions=PermissionManager(
                PermissionMode.from_string(permission_mode), approver=approver
            ),
            events=events,
            cwd=self.cwd,
            tool_names=list(tools) if tools is not None else None,
            system_prompt=system_prompt,
            append_system_prompt=append_system_prompt,
            stream=stream_text,
            persist=persist,
            max_turns=max_turns,
            max_budget_usd=max_budget_usd,
            max_request_tokens=max_request_tokens,
        )
        if resume:
            self._resume(resume)

    # ------------------------------------------------------------------ API

    @property
    def session_id(self) -> str:
        return self.agent.session_id

    @property
    def messages(self) -> List[Dict[str, Any]]:
        """The conversation so far (OpenAI message format)."""
        return self.agent.messages

    def send(self, prompt: str, images: Sequence[Union[str, Path]] = ()) -> Result:
        """Run one request to completion and return its result."""
        response = self.agent.run(prompt, images=[Path(p) for p in images])
        meta = response.metadata
        result = Result(
            text=response.text,
            session_id=self.session_id,
            turns=int(meta.get("turns") or 0),
            tool_calls=int(meta.get("tool_calls") or 0),
            usage=dict(meta.get("request_usage") or meta.get("usage") or {}),
            cost_usd=meta.get("cost_usd"),
            model=meta.get("model"),
            stopped=meta.get("stopped"),
            metadata=meta,
        )
        self._emit(result.to_event())
        return result

    def stream(self, prompt: str, images: Sequence[Union[str, Path]] = ()) -> Iterator[Event]:
        """Run one request, yielding events as they happen (ends with the result)."""
        events: "queue.Queue[Optional[Event]]" = queue.Queue()
        failure: List[BaseException] = []
        self._handlers.append(events.put)

        def worker() -> None:
            try:
                self.send(prompt, images)
            except BaseException as e:  # re-raised in the caller's thread
                failure.append(e)
            finally:
                events.put(None)

        thread = threading.Thread(target=worker, name="joshu-session", daemon=True)
        thread.start()
        try:
            while True:
                event = events.get()
                if event is None:
                    break
                yield event
        finally:
            thread.join()
            self._handlers.remove(events.put)
        if failure:
            raise failure[0]

    def close(self) -> None:
        """End the session (runs session_end hooks)."""
        self.agent.end_session()

    def __enter__(self) -> "Session":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    # -------------------------------------------------------------- helpers

    def _emit(self, event: Event) -> None:
        for handler in list(self._handlers):
            handler(event)

    def _resume(self, resume: str) -> None:
        from joshu.core.sessions import SessionError, latest_session, load_session

        if resume == "last":
            info = latest_session(self.cwd)
            if info is None:
                raise SessionError("No saved session in this directory")
            resume = info.id
        self.agent.restore(load_session(resume))


def run(prompt: str, **options: Any) -> Result:
    """Run one request in a new session; options are those of `Session`."""
    with Session(**options) as session:
        return session.send(prompt)
