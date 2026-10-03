"""
Runs the tool-using Agent for an A2A task.

The Agent is synchronous, so it runs in a worker thread. Its progress
(streamed text, tool calls, approval requests) is pushed onto an asyncio queue
that the executor turns into A2A events. Approvals block the agent thread
until the client answers through /tasks/{id}/confirm; cancelling the task
stops the agent at its next step.
"""

from __future__ import annotations

import asyncio
import threading
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Tuple

from joshu.a2a.events import ConfirmationOption
from joshu.a2a.task import AgentSettings
from joshu.core.agent import Agent, AgentEvents, AgentResponse
from joshu.core.llm_client import ChatClient, create_chat_client
from joshu.core.permissions import (
    ApprovalChoice,
    ApprovalRequest,
    PermissionManager,
    PermissionMode,
)

# A2A approval modes -> permission modes
APPROVAL_MODES = {
    "safe_only": PermissionMode.DEFAULT,
    "default": PermissionMode.DEFAULT,
    "accept_edits": PermissionMode.ACCEPT_EDITS,
    "plan": PermissionMode.PLAN,
    "auto": PermissionMode.BYPASS,
    "bypass": PermissionMode.BYPASS,
}

_RESPONSES = {
    ConfirmationOption.PROCEED_ONCE.value: ApprovalChoice.YES,
    ConfirmationOption.PROCEED_SESSION.value: ApprovalChoice.ALWAYS,
    ConfirmationOption.CANCEL.value: ApprovalChoice.NO,
    ConfirmationOption.CANCEL_TASK.value: ApprovalChoice.NO,
}

ClientFactory = Callable[[AgentSettings], ChatClient]


class TaskCancelled(Exception):
    """Raised inside the agent thread to stop a cancelled task."""


def default_client_factory(settings: AgentSettings) -> ChatClient:
    model = None if settings.model in ("", "default") else settings.model
    return create_chat_client(model)


@dataclass
class _PendingApproval:
    request: ApprovalRequest
    answered: threading.Event = field(default_factory=threading.Event)
    choice: ApprovalChoice = ApprovalChoice.NO


class AgentTaskRunner:
    """One agent run for one A2A task."""

    def __init__(
        self,
        prompt: str,
        settings: AgentSettings,
        client_factory: ClientFactory = default_client_factory,
    ) -> None:
        self.prompt = prompt
        self.settings = settings
        self.client_factory = client_factory
        self.cancelled = threading.Event()
        self._pending: Dict[str, _PendingApproval] = {}
        self._emit: Callable[[Tuple[Any, ...]], None] = lambda item: None

    # ------------------------------------------------- called from asyncio

    async def run(self):
        """
        Run the agent and yield its progress as tuples:

            ("text", delta)
            ("tool_start", name, arguments)
            ("tool_end", name, output, success)
            ("confirm", call_id, ApprovalRequest)
            ("done", AgentResponse) | ("cancelled",) | ("error", message)
        """
        loop = asyncio.get_running_loop()
        queue: asyncio.Queue = asyncio.Queue()
        self._emit = lambda item: loop.call_soon_threadsafe(queue.put_nowait, item)
        worker = loop.run_in_executor(None, self._run_agent)

        while True:
            item = await queue.get()
            yield item
            if item[0] in ("done", "cancelled", "error"):
                break
        await worker

    def respond(self, call_id: str, response: str) -> bool:
        """Answer a pending approval; False if the call id isn't pending."""
        pending = self._pending.get(call_id)
        if pending is None or response not in _RESPONSES:
            return False
        pending.choice = _RESPONSES[response]
        pending.answered.set()
        if response == ConfirmationOption.CANCEL_TASK.value:
            self.cancel()
        return True

    def has_pending(self, call_id: str) -> bool:
        return call_id in self._pending

    def cancel(self) -> None:
        self.cancelled.set()
        for pending in list(self._pending.values()):
            pending.choice = ApprovalChoice.NO
            pending.answered.set()

    # ------------------------------------------------- agent thread

    def _run_agent(self) -> None:
        try:
            from joshu.tools.filesystem_tools import set_workspace_root
            from joshu.tools.shell_tool import get_shell_config

            cwd = Path(self.settings.target_directory).resolve()
            # File and shell tools resolve paths from process-wide settings,
            # so a server handles one target directory at a time
            set_workspace_root(cwd)
            get_shell_config().working_directory = str(cwd)

            mode = APPROVAL_MODES.get(self.settings.approval_mode, PermissionMode.DEFAULT)
            agent = Agent(
                client=self.client_factory(self.settings),
                permissions=PermissionManager(mode, approver=self._approve),
                events=_RunnerEvents(self),
                system_prompt=self.settings.system_prompt,
                cwd=cwd,
                tool_names=None if self.settings.tools_enabled else [],
            )
            response: AgentResponse = agent.run(self.prompt)
        except TaskCancelled:
            self._emit(("cancelled",))
        except Exception as e:  # reported to the client as an error event
            self._emit(("error", str(e)))
        else:
            if self.cancelled.is_set():
                self._emit(("cancelled",))
            else:
                self._emit(("done", response))

    def _approve(self, request: ApprovalRequest) -> ApprovalChoice:
        if self.cancelled.is_set():
            return ApprovalChoice.NO
        call_id = f"approval_{uuid.uuid4().hex[:12]}"
        pending = _PendingApproval(request)
        self._pending[call_id] = pending
        self._emit(("confirm", call_id, request))
        pending.answered.wait()
        del self._pending[call_id]
        return pending.choice

    def check_cancelled(self) -> None:
        if self.cancelled.is_set():
            raise TaskCancelled()


class _RunnerEvents(AgentEvents):
    def __init__(self, runner: AgentTaskRunner) -> None:
        self.runner = runner

    def on_text(self, delta: str) -> None:
        self.runner.check_cancelled()
        self.runner._emit(("text", delta))

    def on_tool_start(self, name: str, arguments: Dict[str, Any]) -> None:
        self.runner.check_cancelled()
        self.runner._emit(("tool_start", name, arguments))

    def on_tool_end(self, name: str, output: str, success: bool) -> None:
        self.runner._emit(("tool_end", name, output, success))


def latest_user_message(messages: List[Any]) -> str:
    """Text of the last user message in an A2A task's chat history."""
    for message in reversed(messages):
        role = getattr(getattr(message, "role", None), "value", getattr(message, "role", None))
        if role == "user":
            return str(getattr(message, "content", "") or "")
    return ""
