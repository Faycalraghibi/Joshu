"""
A2A Task management for agent execution lifecycle.

This module defines the Task class that wraps agent execution state,
mapping to existing ChatSession and tool scheduler components.

NOTE: This module provides transport and orchestration only.
It must not introduce new agent logic or execution semantics.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional
from uuid import uuid4

from joshu.core.chat_session import ChatSession, ChatSessionConfig, SessionState
from joshu.core.tool_scheduler import CoreToolScheduler, ToolSchedulerConfig

logger = logging.getLogger(__name__)


class TaskState(Enum):
    """
    A2A task states.

    Maps to existing SessionState to maintain compatibility
    without introducing new execution semantics.
    """

    SUBMITTED = "submitted"  # Task created, not yet started
    INPUT_REQUIRED = "input-required"  # Awaiting user confirmation
    WORKING = "working"  # Actively executing
    CANCELED = "canceled"  # Canceled by user or client disconnect
    FAILED = "failed"  # Execution failed
    COMPLETED = "completed"  # Successfully completed


# Mapping from SessionState to TaskState
_SESSION_STATE_MAP = {
    SessionState.INITIALIZED: TaskState.SUBMITTED,
    SessionState.ACTIVE: TaskState.WORKING,
    SessionState.PAUSED: TaskState.INPUT_REQUIRED,
    SessionState.COMPLETED: TaskState.COMPLETED,
    SessionState.ERROR: TaskState.FAILED,
}


class AbortController:
    """
    Controller for canceling async operations.

    Provides a signal that can be checked by async operations
    to determine if they should abort.
    """

    def __init__(self) -> None:
        self._aborted = False
        self._reason: Optional[str] = None
        self._event = asyncio.Event()

    @property
    def aborted(self) -> bool:
        """Check if abort has been signaled."""
        return self._aborted

    @property
    def reason(self) -> Optional[str]:
        """Get the abort reason if aborted."""
        return self._reason

    def abort(self, reason: str = "Canceled") -> None:
        """Signal abort to all listeners."""
        self._aborted = True
        self._reason = reason
        self._event.set()
        logger.info(f"Abort signaled: {reason}")

    async def wait_for_abort(self) -> None:
        """Wait until abort is signaled."""
        await self._event.wait()

    def check(self) -> None:
        """
        Check if aborted and raise if so.

        Raises:
            asyncio.CancelledError: If abort has been signaled
        """
        if self._aborted:
            raise asyncio.CancelledError(self._reason or "Aborted")


@dataclass
class AgentSettings:
    """
    Configuration settings for an agent task.

    Captures the settings used when creating a task,
    enabling task reconstruction from persisted state.

    Attributes:
        model: Model name or alias to use
        target_directory: Working directory for the task
        tools_enabled: Whether tool calling is enabled
        approval_mode: Tool approval mode
        system_prompt: Optional system prompt override
        extensions: List of enabled extensions
    """

    model: str = "default"
    target_directory: str = "."
    tools_enabled: bool = True
    approval_mode: str = "safe_only"
    system_prompt: Optional[str] = None
    extensions: list = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "model": self.model,
            "target_directory": self.target_directory,
            "tools_enabled": self.tools_enabled,
            "approval_mode": self.approval_mode,
            "system_prompt": self.system_prompt,
            "extensions": self.extensions,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AgentSettings":
        """Create from dictionary."""
        return cls(
            model=data.get("model", "default"),
            target_directory=data.get("target_directory", "."),
            tools_enabled=data.get("tools_enabled", True),
            approval_mode=data.get("approval_mode", "safe_only"),
            system_prompt=data.get("system_prompt"),
            extensions=data.get("extensions", []),
        )


@dataclass
class Task:
    """
    Agent task wrapping execution state.

    This class encapsulates a single agent task, managing its
    lifecycle and providing access to the underlying components.

    Does NOT execute - only tracks state. Execution is handled
    by AgentExecutor.

    Attributes:
        task_id: Unique identifier for the task
        state: Current task state
        settings: Agent settings for this task
        session: Chat session managing conversation
        scheduler: Tool scheduler for this task
        created_at: When the task was created
        updated_at: When the task was last updated
        abort_controller: Controller for canceling the task
        pending_confirmation: ID of tool call awaiting confirmation
        metadata: Additional task metadata
    """

    task_id: str
    state: TaskState
    settings: AgentSettings
    session: ChatSession
    scheduler: CoreToolScheduler
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    abort_controller: Optional[AbortController] = None
    pending_confirmation: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def create(
        cls,
        settings: AgentSettings,
        task_id: Optional[str] = None,
    ) -> "Task":
        """
        Create a new task with the given settings.

        Args:
            settings: Agent settings for the task
            task_id: Optional task ID (generated if not provided)

        Returns:
            New Task instance in SUBMITTED state
        """
        task_id = task_id or str(uuid4())

        # Create session config from settings
        session_config = ChatSessionConfig(
            model=settings.model,
            system_prompt=settings.system_prompt,
            tools_enabled=settings.tools_enabled,
        )

        # Create scheduler config from settings
        scheduler_config = ToolSchedulerConfig()

        logger.info(f"Creating task {task_id} with model {settings.model}")

        return cls(
            task_id=task_id,
            state=TaskState.SUBMITTED,
            settings=settings,
            session=ChatSession(session_config),
            scheduler=CoreToolScheduler(scheduler_config),
            abort_controller=AbortController(),
        )

    def transition_to(self, new_state: TaskState) -> None:
        """
        Transition to a new state.

        Args:
            new_state: The new state to transition to

        Raises:
            ValueError: If the transition is invalid
        """
        old_state = self.state
        self.state = new_state
        self.updated_at = datetime.now()
        logger.info(f"Task {self.task_id}: {old_state.value} -> {new_state.value}")

    def start(self) -> None:
        """Start task execution (SUBMITTED -> WORKING)."""
        if self.state == TaskState.SUBMITTED:
            self.transition_to(TaskState.WORKING)
            self.session.start()

    def request_input(self, call_id: str) -> None:
        """Mark task as requiring user input."""
        self.pending_confirmation = call_id
        self.transition_to(TaskState.INPUT_REQUIRED)

    def resume(self) -> None:
        """Resume task after input received."""
        self.pending_confirmation = None
        self.transition_to(TaskState.WORKING)

    def complete(self) -> None:
        """Mark task as completed."""
        self.transition_to(TaskState.COMPLETED)

    def fail(self, error: str) -> None:
        """Mark task as failed."""
        self.metadata["error"] = error
        self.transition_to(TaskState.FAILED)

    def cancel(self, reason: str = "Canceled by user") -> None:
        """Cancel the task."""
        if self.abort_controller:
            self.abort_controller.abort(reason)
        self.metadata["cancel_reason"] = reason
        self.transition_to(TaskState.CANCELED)

    @property
    def is_terminal(self) -> bool:
        """Check if task is in a terminal state."""
        return self.state in (TaskState.COMPLETED, TaskState.FAILED, TaskState.CANCELED)

    @property
    def is_active(self) -> bool:
        """Check if task is actively executing."""
        return self.state == TaskState.WORKING

    def to_dict(self) -> Dict[str, Any]:
        """Serialize task to dictionary for persistence."""
        return {
            "task_id": self.task_id,
            "state": self.state.value,
            "settings": self.settings.to_dict(),
            "session_state": {
                "session_id": self.session.session_id,
                "history": [msg.to_dict() for msg in self.session.history.messages],
            },
            "scheduler_state": {
                "pending_calls": [call.to_dict() for call in self.scheduler.get_pending()],
            },
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "pending_confirmation": self.pending_confirmation,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Task":
        """
        Reconstruct task from serialized dictionary.

        Args:
            data: Serialized task data

        Returns:
            Reconstructed Task instance
        """
        settings = AgentSettings.from_dict(data["settings"])

        # Create session and scheduler
        session_config = ChatSessionConfig(
            model=settings.model,
            system_prompt=settings.system_prompt,
            tools_enabled=settings.tools_enabled,
        )
        session = ChatSession(session_config, session_id=data["session_state"]["session_id"])

        # Restore history
        from joshu.core.chat_session import ChatMessage

        for msg_data in data["session_state"]["history"]:
            # Reconstruct message from dict
            msg = ChatMessage(
                role=msg_data["role"],
                content=msg_data["content"],
            )
            session.history.add(msg)

        scheduler = CoreToolScheduler()

        task = cls(
            task_id=data["task_id"],
            state=TaskState(data["state"]),
            settings=settings,
            session=session,
            scheduler=scheduler,
            created_at=datetime.fromisoformat(data["created_at"]),
            updated_at=datetime.fromisoformat(data["updated_at"]),
            abort_controller=AbortController(),
            pending_confirmation=data.get("pending_confirmation"),
            metadata=data.get("metadata", {}),
        )

        logger.info(f"Reconstructed task {task.task_id} in state {task.state.value}")
        return task
