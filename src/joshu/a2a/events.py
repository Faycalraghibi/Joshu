"""
A2A Event types for structured agent communication.

This module defines event types for communicating agent state,
tool calls, and confirmation requests to external clients.

NOTE: This module provides transport and orchestration only.
It must not introduce new agent logic or execution semantics.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


class EventType(Enum):
    """Types of events emitted during agent execution."""

    THOUGHT = "thought"  # Agent's internal reasoning
    TOOL_CALL = "tool_call"  # Tool invocation request
    TOOL_RESULT = "tool_result"  # Tool execution result
    CONFIRMATION_REQUEST = "confirmation_request"  # Approval needed
    CONFIRMATION_RESPONSE = "confirmation_response"  # User response
    STATE_CHANGE = "state_change"  # Task state transition
    MESSAGE = "message"  # Agent text response
    ERROR = "error"  # Error occurred
    COMPLETE = "complete"  # Task completed


class ConfirmationOption(Enum):
    """Options for confirmation responses."""

    PROCEED_ONCE = "proceed_once"  # Execute this tool once
    PROCEED_SESSION = "proceed_session"  # Auto-approve for session
    CANCEL = "cancel"  # Cancel the tool call
    CANCEL_TASK = "cancel_task"  # Cancel the entire task


@dataclass
class AgentThought:
    """
    Agent's internal reasoning step.

    Represents thinking/planning output from the agent that
    is surfaced to clients for transparency.

    Attributes:
        content: The reasoning text
        turn_number: Current conversation turn
        timestamp: When the thought occurred
    """

    content: str
    turn_number: int = 0
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "content": self.content,
            "turn_number": self.turn_number,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class ToolCallEvent:
    """
    Tool invocation request event.

    Represents a tool call made by the agent, including
    its arguments and current status.

    Attributes:
        tool_name: Name of the tool to execute
        arguments: Arguments for the tool
        call_id: Unique identifier for this call
        status: Current status (pending, executing, completed, failed)
    """

    tool_name: str
    arguments: Dict[str, Any]
    call_id: str
    status: str = "pending"
    result: Optional[str] = None
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "tool_name": self.tool_name,
            "arguments": self.arguments,
            "call_id": self.call_id,
            "status": self.status,
            "result": self.result,
            "error": self.error,
        }


@dataclass
class ConfirmationRequest:
    """
    Request for user approval of tool execution.

    When a tool requires user consent before execution,
    this event is emitted to prompt the user.

    Attributes:
        call_id: ID of the tool call awaiting confirmation
        tool_name: Name of the tool
        description: Human-readable description of what will happen
        arguments: Tool arguments for review
        options: Available response options
    """

    call_id: str
    tool_name: str
    description: str
    arguments: Dict[str, Any] = field(default_factory=dict)
    options: List[str] = field(
        default_factory=lambda: [
            ConfirmationOption.PROCEED_ONCE.value,
            ConfirmationOption.CANCEL.value,
        ]
    )

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "call_id": self.call_id,
            "tool_name": self.tool_name,
            "description": self.description,
            "arguments": self.arguments,
            "options": self.options,
        }


@dataclass
class AgentExecutionEvent:
    """
    Event emitted during agent execution.

    This is the unified event structure streamed to clients
    via SSE. All execution events are wrapped in this format.

    Attributes:
        event_type: Type of event (thought, tool_call, etc.)
        data: Event-specific payload
        task_id: ID of the task this event belongs to
        timestamp: When the event occurred
        sequence: Monotonically increasing sequence number
    """

    event_type: EventType
    data: Dict[str, Any]
    task_id: str
    timestamp: datetime = field(default_factory=datetime.now)
    sequence: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "event_type": self.event_type.value,
            "data": self.data,
            "task_id": self.task_id,
            "timestamp": self.timestamp.isoformat(),
            "sequence": self.sequence,
        }

    def to_sse(self) -> str:
        """
        Format for Server-Sent Events.

        Returns:
            SSE-formatted string with event type and JSON data
        """
        event_data = json.dumps(self.to_dict())
        return f"event: {self.event_type.value}\ndata: {event_data}\n\n"

    @classmethod
    def thought(
        cls, task_id: str, thought: AgentThought, sequence: int = 0
    ) -> "AgentExecutionEvent":
        """Create a thought event."""
        return cls(
            event_type=EventType.THOUGHT,
            data=thought.to_dict(),
            task_id=task_id,
            sequence=sequence,
        )

    @classmethod
    def tool_call(
        cls, task_id: str, tool_event: ToolCallEvent, sequence: int = 0
    ) -> "AgentExecutionEvent":
        """Create a tool call event."""
        return cls(
            event_type=EventType.TOOL_CALL,
            data=tool_event.to_dict(),
            task_id=task_id,
            sequence=sequence,
        )

    @classmethod
    def confirmation(
        cls, task_id: str, request: ConfirmationRequest, sequence: int = 0
    ) -> "AgentExecutionEvent":
        """Create a confirmation request event."""
        return cls(
            event_type=EventType.CONFIRMATION_REQUEST,
            data=request.to_dict(),
            task_id=task_id,
            sequence=sequence,
        )

    @classmethod
    def state_change(
        cls, task_id: str, old_state: str, new_state: str, sequence: int = 0
    ) -> "AgentExecutionEvent":
        """Create a state change event."""
        return cls(
            event_type=EventType.STATE_CHANGE,
            data={"old_state": old_state, "new_state": new_state},
            task_id=task_id,
            sequence=sequence,
        )

    @classmethod
    def message(cls, task_id: str, content: str, sequence: int = 0) -> "AgentExecutionEvent":
        """Create a message event."""
        return cls(
            event_type=EventType.MESSAGE,
            data={"content": content},
            task_id=task_id,
            sequence=sequence,
        )

    @classmethod
    def error(
        cls, task_id: str, error: str, code: Optional[str] = None, sequence: int = 0
    ) -> "AgentExecutionEvent":
        """Create an error event."""
        return cls(
            event_type=EventType.ERROR,
            data={"error": error, "code": code},
            task_id=task_id,
            sequence=sequence,
        )

    @classmethod
    def complete(
        cls, task_id: str, result: Optional[str] = None, sequence: int = 0
    ) -> "AgentExecutionEvent":
        """Create a completion event."""
        return cls(
            event_type=EventType.COMPLETE,
            data={"result": result},
            task_id=task_id,
            sequence=sequence,
        )
