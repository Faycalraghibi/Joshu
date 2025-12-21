"""
Agent-to-Agent (A2A) Communication Server for Joshu.

This package provides transport and orchestration for exposing Joshu agent
capabilities to external clients via HTTP/SSE.

NOTE: This module provides transport and orchestration only.
It must not introduce new agent logic or execution semantics.
"""

from joshu.a2a.event_bus import ExecutionEventBus, get_event_bus
from joshu.a2a.events import (
    AgentExecutionEvent,
    AgentThought,
    ConfirmationOption,
    ConfirmationRequest,
    EventType,
    ToolCallEvent,
)
from joshu.a2a.executor import (
    AgentExecutor,
    TaskCancelledError,
    TaskNotFoundError,
    get_agent_executor,
)
from joshu.a2a.task import AbortController, AgentSettings, Task, TaskState
from joshu.a2a.task_store import (
    InMemoryTaskStore,
    NoOpTaskStore,
    TaskStore,
    get_task_store,
    set_task_store,
)

__all__ = [
    # Events
    "AgentExecutionEvent",
    "AgentThought",
    "ConfirmationOption",
    "ConfirmationRequest",
    "EventType",
    "ToolCallEvent",
    # Task
    "AbortController",
    "AgentSettings",
    "Task",
    "TaskState",
    # Task Store
    "InMemoryTaskStore",
    "NoOpTaskStore",
    "TaskStore",
    "get_task_store",
    "set_task_store",
    # Event Bus
    "ExecutionEventBus",
    "get_event_bus",
    # Executor
    "AgentExecutor",
    "TaskCancelledError",
    "TaskNotFoundError",
    "get_agent_executor",
]
