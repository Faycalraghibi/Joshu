"""
A2A Agent Executor for task orchestration.

This module provides the AgentExecutor that orchestrates task lifecycle,
bridging A2A with existing Joshu components.

NOTE: This module provides transport and orchestration only.
It must not introduce new agent logic or execution semantics.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, AsyncIterator, Dict, List, Optional

from joshu.a2a.agent_runner import (
    AgentTaskRunner,
    ClientFactory,
    default_client_factory,
    latest_user_message,
)
from joshu.a2a.event_bus import ExecutionEventBus, get_event_bus
from joshu.a2a.events import (
    AgentExecutionEvent,
    AgentThought,
    ConfirmationOption,
    ConfirmationRequest,
    ToolCallEvent,
)
from joshu.a2a.task import AgentSettings, Task, TaskState
from joshu.a2a.task_store import TaskStore, get_task_store
from joshu.core.tool_executor import ToolExecutor, get_tool_executor
from joshu.core.tool_scheduler import ScheduledToolCall, ToolCallStatus

logger = logging.getLogger(__name__)


class TaskNotFoundError(Exception):
    """Raised when a task is not found."""

    pass


class TaskCancelledError(Exception):
    """Raised when a task is cancelled."""

    pass


class AgentExecutor:
    """
    Orchestrates task lifecycle without adding agent logic.

    This class bridges A2A with existing Joshu components:
    - Creates and manages Task instances
    - Delegates to CoreToolScheduler for tool scheduling
    - Delegates to ToolExecutor for tool execution
    - Publishes events via ExecutionEventBus
    - Persists state via TaskStore

    Does NOT:
    - Change agent prompt logic
    - Add new task states
    - Modify tool scheduler behavior
    - Introduce retries or backoff

    Example:
        >>> executor = AgentExecutor()
        >>> task = await executor.create_task("List files", settings)
        >>> async for event in executor.execute_task(task.task_id):
        ...     print(event.to_sse())
    """

    def __init__(
        self,
        task_store: Optional[TaskStore] = None,
        event_bus: Optional[ExecutionEventBus] = None,
        tool_executor: Optional[ToolExecutor] = None,
        client_factory: Optional[ClientFactory] = None,
    ) -> None:
        """
        Initialize the executor.

        Args:
            task_store: TaskStore for persistence (defaults to global)
            event_bus: EventBus for streaming (defaults to global)
            tool_executor: ToolExecutor for tool calls (defaults to global)
            client_factory: Builds the model client for a task's settings
                (defaults to the configured provider)
        """
        self._task_store = task_store or get_task_store()
        self._event_bus = event_bus or get_event_bus()
        self._tool_executor = tool_executor or get_tool_executor()
        self._active_tasks: Dict[str, Task] = {}
        self._sequence_counters: Dict[str, int] = {}
        self._client_factory = client_factory or default_client_factory
        self._runners: Dict[str, AgentTaskRunner] = {}

    async def _publish(self, event: AgentExecutionEvent) -> AgentExecutionEvent:
        await self._event_bus.publish(event)
        return event

    def _next_sequence(self, task_id: str) -> int:
        """Get next sequence number for a task."""
        if task_id not in self._sequence_counters:
            self._sequence_counters[task_id] = 0
        self._sequence_counters[task_id] += 1
        return self._sequence_counters[task_id]

    async def create_task(
        self,
        message: str,
        settings: Optional[AgentSettings] = None,
    ) -> Task:
        """
        Create a new task.

        Args:
            message: Initial user message
            settings: Agent settings (defaults to default settings)

        Returns:
            New Task instance in SUBMITTED state
        """
        settings = settings or AgentSettings()
        task = Task.create(settings)

        from joshu.core.chat_session import ChatMessage

        task.session.history.add(ChatMessage.user(message))

        self._active_tasks[task.task_id] = task
        self._task_store.save(task)
        self._sequence_counters[task.task_id] = 0

        logger.info(f"Created task {task.task_id}")

        event = AgentExecutionEvent.state_change(
            task_id=task.task_id,
            old_state="none",
            new_state=TaskState.SUBMITTED.value,
            sequence=self._next_sequence(task.task_id),
        )
        await self._event_bus.publish(event)

        return task

    async def get_task(self, task_id: str) -> Task:
        """
        Get a task by ID.

        Args:
            task_id: Task ID to retrieve

        Returns:
            Task instance

        Raises:
            TaskNotFoundError: If task not found
        """
        # Check active tasks first
        if task_id in self._active_tasks:
            return self._active_tasks[task_id]

        # Try loading from store
        task = self._task_store.get(task_id)
        if task is None:
            raise TaskNotFoundError(f"Task not found: {task_id}")

        self._active_tasks[task_id] = task
        return task

    async def execute_task(self, task_id: str) -> AsyncIterator[AgentExecutionEvent]:
        """
        Execute a task, streaming events.

        This is the main execution loop that:
        1. Transitions task to WORKING
        2. Processes scheduled tool calls
        3. Handles confirmation flow
        4. Publishes events for each step

        Uses existing ToolExecutor and CoreToolScheduler.

        Args:
            task_id: ID of task to execute

        Yields:
            AgentExecutionEvent for each execution step
        """
        task = await self.get_task(task_id)

        # Start task
        old_state = task.state.value
        task.start()
        self._task_store.save(task)

        # Publish state change
        state_event = AgentExecutionEvent.state_change(
            task_id=task_id,
            old_state=old_state,
            new_state=task.state.value,
            sequence=self._next_sequence(task_id),
        )
        await self._event_bus.publish(state_event)
        yield state_event

        try:
            prompt = latest_user_message(task.session.history.messages)
            runner = AgentTaskRunner(prompt, task.settings, self._client_factory)
            self._runners[task_id] = runner

            text_parts: List[str] = []
            result_text = ""
            cancelled = False
            async for item in runner.run():
                kind = item[0]
                if kind == "text":
                    text_parts.append(item[1])
                    continue
                # Text the model wrote before acting is its reasoning for that step
                if kind in ("tool_start", "confirm") and "".join(text_parts).strip():
                    thought = AgentThought(content="".join(text_parts).strip())
                    yield await self._publish(
                        AgentExecutionEvent.thought(task_id, thought, self._next_sequence(task_id))
                    )
                text_parts = [] if kind in ("tool_start", "confirm") else text_parts

                if kind == "tool_start":
                    tool_event = ToolCallEvent(
                        tool_name=item[1], arguments=item[2], call_id="", status="executing"
                    )
                    yield await self._publish(
                        AgentExecutionEvent.tool_call(
                            task_id, tool_event, self._next_sequence(task_id)
                        )
                    )
                elif kind == "tool_end":
                    success = item[3]
                    tool_event = ToolCallEvent(
                        tool_name=item[1],
                        arguments={},
                        call_id="",
                        status="completed" if success else "failed",
                        result=item[2] if success else None,
                        error=None if success else item[2],
                    )
                    yield await self._publish(
                        AgentExecutionEvent.tool_call(
                            task_id, tool_event, self._next_sequence(task_id)
                        )
                    )
                elif kind == "confirm":
                    call_id, request = item[1], item[2]
                    task.request_input(call_id)
                    self._task_store.save(task)
                    confirmation = ConfirmationRequest(
                        call_id=call_id,
                        tool_name=request.tool_name,
                        description=request.preview,
                        arguments=request.arguments,
                        options=[option.value for option in ConfirmationOption],
                    )
                    yield await self._publish(
                        AgentExecutionEvent.confirmation(
                            task_id, confirmation, self._next_sequence(task_id)
                        )
                    )
                elif kind == "done":
                    result_text = item[1].text
                elif kind == "cancelled":
                    cancelled = True
                elif kind == "error":
                    raise RuntimeError(item[1])

            if cancelled:
                if not task.is_terminal:
                    task.cancel("Canceled")
                    self._task_store.save(task)
                return

            if result_text:
                yield await self._publish(
                    AgentExecutionEvent.message(task_id, result_text, self._next_sequence(task_id))
                )

            task.complete()
            self._task_store.save(task)
            yield await self._publish(
                AgentExecutionEvent.complete(
                    task_id=task_id,
                    result=result_text,
                    sequence=self._next_sequence(task_id),
                )
            )

        except asyncio.CancelledError:
            task.cancel("Cancelled by client")
            self._task_store.save(task)

            error_event = AgentExecutionEvent.state_change(
                task_id=task_id,
                old_state=TaskState.WORKING.value,
                new_state=TaskState.CANCELED.value,
                sequence=self._next_sequence(task_id),
            )
            await self._event_bus.publish(error_event)
            yield error_event

        except Exception as e:
            logger.error(f"Task {task_id} failed: {e}", exc_info=True)
            task.fail(str(e))
            self._task_store.save(task)

            error_event = AgentExecutionEvent.error(
                task_id=task_id,
                error=str(e),
                sequence=self._next_sequence(task_id),
            )
            await self._event_bus.publish(error_event)
            yield error_event

        finally:
            self._runners.pop(task_id, None)
            await self._event_bus.end_task(task_id)

    async def _process_tool_calls(self, task: Task) -> AsyncIterator[AgentExecutionEvent]:
        """
        Process scheduled tool calls for a task.

        Uses existing CoreToolScheduler and ToolExecutor.

        Args:
            task: The task to process

        Yields:
            Events for each tool call step
        """
        # Check for abort
        if task.abort_controller and task.abort_controller.aborted:
            raise asyncio.CancelledError("Task aborted")

        # Get pending tool calls from scheduler
        pending = task.scheduler.get_pending()

        for scheduled_call in pending:
            # Check if requires confirmation
            if scheduled_call.requires_approval and scheduled_call.status == ToolCallStatus.PENDING:
                # Emit confirmation request
                async for event in self._request_confirmation(task, scheduled_call):
                    yield event
                continue

            # Execute approved calls
            if scheduled_call.status in (ToolCallStatus.APPROVED, ToolCallStatus.PENDING):
                async for event in self._execute_tool_call(task, scheduled_call):
                    yield event

    async def _request_confirmation(
        self, task: Task, scheduled_call: ScheduledToolCall
    ) -> AsyncIterator[AgentExecutionEvent]:
        """
        Request user confirmation for a tool call.

        Args:
            task: The task
            scheduled_call: The tool call awaiting confirmation

        Yields:
            Confirmation request event
        """
        task.request_input(scheduled_call.call_id)
        self._task_store.save(task)

        request = ConfirmationRequest(
            call_id=scheduled_call.call_id,
            tool_name=scheduled_call.tool_name,
            description=f"Execute {scheduled_call.tool_name}?",
            arguments=scheduled_call.arguments,
        )

        event = AgentExecutionEvent.confirmation(
            task_id=task.task_id,
            request=request,
            sequence=self._next_sequence(task.task_id),
        )
        await self._event_bus.publish(event)
        yield event

    async def _execute_tool_call(
        self, task: Task, scheduled_call: ScheduledToolCall
    ) -> AsyncIterator[AgentExecutionEvent]:
        """
        Execute a tool call using existing ToolExecutor.

        Args:
            task: The task
            scheduled_call: The tool call to execute

        Yields:
            Tool call and result events
        """
        # Emit tool call event
        tool_event = ToolCallEvent(
            tool_name=scheduled_call.tool_name,
            arguments=scheduled_call.arguments,
            call_id=scheduled_call.call_id,
            status="executing",
        )

        event = AgentExecutionEvent.tool_call(
            task_id=task.task_id,
            tool_event=tool_event,
            sequence=self._next_sequence(task.task_id),
        )
        await self._event_bus.publish(event)
        yield event

        # Execute via existing ToolExecutor
        try:
            result = self._tool_executor.execute_tool(
                scheduled_call.tool_name,
                scheduled_call.arguments,
            )

            if result["success"]:
                scheduled_call.mark_completed(str(result["result"]))
            else:
                scheduled_call.mark_failed(result["error"] or "Unknown error")

        except Exception as e:
            scheduled_call.mark_failed(str(e))

        # Emit result event
        tool_event = ToolCallEvent(
            tool_name=scheduled_call.tool_name,
            arguments=scheduled_call.arguments,
            call_id=scheduled_call.call_id,
            status="completed" if scheduled_call.status == ToolCallStatus.COMPLETED else "failed",
            result=scheduled_call.result,
            error=scheduled_call.error,
        )

        result_event = AgentExecutionEvent.tool_call(
            task_id=task.task_id,
            tool_event=tool_event,
            sequence=self._next_sequence(task.task_id),
        )
        await self._event_bus.publish(result_event)
        yield result_event

    async def cancel_task(self, task_id: str, reason: str = "Canceled by user") -> bool:
        """
        Cancel a running task.

        Args:
            task_id: ID of task to cancel
            reason: Cancellation reason

        Returns:
            True if canceled, False if task not found or already terminal
        """
        try:
            task = await self.get_task(task_id)
        except TaskNotFoundError:
            return False

        if task.is_terminal:
            return False

        task.cancel(reason)
        self._task_store.save(task)
        runner = self._runners.get(task_id)
        if runner is not None:
            runner.cancel()

        # Publish state change
        event = AgentExecutionEvent.state_change(
            task_id=task_id,
            old_state=TaskState.WORKING.value,
            new_state=TaskState.CANCELED.value,
            sequence=self._next_sequence(task_id),
        )
        await self._event_bus.publish(event)
        await self._event_bus.end_task(task_id)

        logger.info(f"Canceled task {task_id}: {reason}")
        return True

    async def respond_to_confirmation(
        self,
        task_id: str,
        call_id: str,
        response: str,
    ) -> bool:
        """
        Respond to a confirmation request.

        Args:
            task_id: Task ID
            call_id: Tool call ID
            response: User response (proceed_once, cancel, etc.)

        Returns:
            True if response processed, False if invalid
        """
        try:
            task = await self.get_task(task_id)
        except TaskNotFoundError:
            return False

        if task.pending_confirmation != call_id:
            logger.warning(
                f"Confirmation mismatch: expected {task.pending_confirmation}, got {call_id}"
            )
            return False

        runner = self._runners.get(task_id)
        if runner is not None and runner.has_pending(call_id):
            if response == ConfirmationOption.CANCEL_TASK.value:
                runner.respond(call_id, response)
                await self.cancel_task(task_id, "Canceled via confirmation")
                return True
            if not runner.respond(call_id, response):
                return False
        # Pre-scheduled tool calls are answered through the scheduler
        elif response == ConfirmationOption.PROCEED_ONCE.value:
            task.scheduler.approve(call_id)
        elif response in (ConfirmationOption.CANCEL.value, ConfirmationOption.CANCEL_TASK.value):
            task.scheduler.reject(call_id)
            if response == ConfirmationOption.CANCEL_TASK.value:
                await self.cancel_task(task_id, "Canceled via confirmation")
                return True

        task.resume()
        self._task_store.save(task)

        # Publish confirmation response event
        event = AgentExecutionEvent(
            event_type=AgentExecutionEvent.state_change(
                task_id, TaskState.INPUT_REQUIRED.value, TaskState.WORKING.value, 0
            ).event_type,
            data={"call_id": call_id, "response": response},
            task_id=task_id,
            sequence=self._next_sequence(task_id),
        )
        await self._event_bus.publish(event)

        return True

    def get_task_metadata(self, task_id: str) -> Dict[str, Any]:
        """
        Get task metadata without full reconstruction.

        Args:
            task_id: Task ID

        Returns:
            Task metadata dictionary
        """
        if task_id in self._active_tasks:
            task = self._active_tasks[task_id]
            return {
                "task_id": task.task_id,
                "state": task.state.value,
                "created_at": task.created_at.isoformat(),
                "updated_at": task.updated_at.isoformat(),
                "is_terminal": task.is_terminal,
                "pending_confirmation": task.pending_confirmation,
            }

        # Check store
        task = self._task_store.get(task_id)
        if task:
            return {
                "task_id": task.task_id,
                "state": task.state.value,
                "created_at": task.created_at.isoformat(),
                "updated_at": task.updated_at.isoformat(),
                "is_terminal": task.is_terminal,
            }

        raise TaskNotFoundError(f"Task not found: {task_id}")


# Module-level executor instance
_executor: Optional[AgentExecutor] = None


def get_agent_executor() -> AgentExecutor:
    """Get the global agent executor instance."""
    global _executor
    if _executor is None:
        _executor = AgentExecutor()
    return _executor
