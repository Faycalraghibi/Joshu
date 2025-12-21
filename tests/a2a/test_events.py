"""
Tests for A2A event types.
"""

import json
from datetime import datetime

from joshu.a2a.events import (
    AgentExecutionEvent,
    AgentThought,
    ConfirmationOption,
    ConfirmationRequest,
    EventType,
    ToolCallEvent,
)


class TestEventType:
    """Tests for EventType enum."""

    def test_event_types_exist(self):
        """Test all required event types exist."""
        assert EventType.THOUGHT.value == "thought"
        assert EventType.TOOL_CALL.value == "tool_call"
        assert EventType.TOOL_RESULT.value == "tool_result"
        assert EventType.CONFIRMATION_REQUEST.value == "confirmation_request"
        assert EventType.STATE_CHANGE.value == "state_change"
        assert EventType.MESSAGE.value == "message"
        assert EventType.ERROR.value == "error"
        assert EventType.COMPLETE.value == "complete"


class TestConfirmationOption:
    """Tests for ConfirmationOption enum."""

    def test_confirmation_options_exist(self):
        """Test all confirmation options exist."""
        assert ConfirmationOption.PROCEED_ONCE.value == "proceed_once"
        assert ConfirmationOption.PROCEED_SESSION.value == "proceed_session"
        assert ConfirmationOption.CANCEL.value == "cancel"
        assert ConfirmationOption.CANCEL_TASK.value == "cancel_task"


class TestAgentThought:
    """Tests for AgentThought dataclass."""

    def test_create_thought(self):
        """Test creating an agent thought."""
        thought = AgentThought(content="Thinking about the problem")
        assert thought.content == "Thinking about the problem"
        assert thought.turn_number == 0
        assert isinstance(thought.timestamp, datetime)

    def test_thought_with_turn(self):
        """Test thought with turn number."""
        thought = AgentThought(content="Step 2", turn_number=2)
        assert thought.turn_number == 2

    def test_thought_to_dict(self):
        """Test serialization."""
        thought = AgentThought(content="Test", turn_number=1)
        data = thought.to_dict()
        assert data["content"] == "Test"
        assert data["turn_number"] == 1
        assert "timestamp" in data


class TestToolCallEvent:
    """Tests for ToolCallEvent dataclass."""

    def test_create_tool_call(self):
        """Test creating a tool call event."""
        event = ToolCallEvent(
            tool_name="read_file",
            arguments={"path": "/test.txt"},
            call_id="call-123",
        )
        assert event.tool_name == "read_file"
        assert event.arguments == {"path": "/test.txt"}
        assert event.call_id == "call-123"
        assert event.status == "pending"
        assert event.result is None
        assert event.error is None

    def test_tool_call_with_result(self):
        """Test tool call with result."""
        event = ToolCallEvent(
            tool_name="read_file",
            arguments={},
            call_id="call-123",
            status="completed",
            result="file contents",
        )
        assert event.status == "completed"
        assert event.result == "file contents"

    def test_tool_call_to_dict(self):
        """Test serialization."""
        event = ToolCallEvent(
            tool_name="shell",
            arguments={"command": "ls"},
            call_id="call-456",
            status="executing",
        )
        data = event.to_dict()
        assert data["tool_name"] == "shell"
        assert data["arguments"] == {"command": "ls"}
        assert data["call_id"] == "call-456"
        assert data["status"] == "executing"


class TestConfirmationRequest:
    """Tests for ConfirmationRequest dataclass."""

    def test_create_confirmation(self):
        """Test creating a confirmation request."""
        request = ConfirmationRequest(
            call_id="call-123",
            tool_name="delete_file",
            description="Delete /important.txt?",
        )
        assert request.call_id == "call-123"
        assert request.tool_name == "delete_file"
        assert request.description == "Delete /important.txt?"
        assert len(request.options) == 2
        assert "proceed_once" in request.options
        assert "cancel" in request.options

    def test_confirmation_with_arguments(self):
        """Test confirmation with tool arguments."""
        request = ConfirmationRequest(
            call_id="call-123",
            tool_name="write_file",
            description="Write to file",
            arguments={"path": "/test.txt", "content": "hello"},
        )
        assert request.arguments["path"] == "/test.txt"

    def test_confirmation_to_dict(self):
        """Test serialization."""
        request = ConfirmationRequest(
            call_id="call-123",
            tool_name="shell",
            description="Run rm -rf?",
        )
        data = request.to_dict()
        assert data["call_id"] == "call-123"
        assert data["tool_name"] == "shell"
        assert data["description"] == "Run rm -rf?"
        assert "options" in data


class TestAgentExecutionEvent:
    """Tests for AgentExecutionEvent dataclass."""

    def test_create_event(self):
        """Test creating an execution event."""
        event = AgentExecutionEvent(
            event_type=EventType.MESSAGE,
            data={"content": "Hello"},
            task_id="task-123",
        )
        assert event.event_type == EventType.MESSAGE
        assert event.data == {"content": "Hello"}
        assert event.task_id == "task-123"
        assert event.sequence == 0

    def test_event_to_dict(self):
        """Test serialization."""
        event = AgentExecutionEvent(
            event_type=EventType.COMPLETE,
            data={"result": "done"},
            task_id="task-456",
            sequence=5,
        )
        data = event.to_dict()
        assert data["event_type"] == "complete"
        assert data["data"] == {"result": "done"}
        assert data["task_id"] == "task-456"
        assert data["sequence"] == 5
        assert "timestamp" in data

    def test_event_to_sse(self):
        """Test SSE formatting."""
        event = AgentExecutionEvent(
            event_type=EventType.MESSAGE,
            data={"content": "Hello"},
            task_id="task-123",
        )
        sse = event.to_sse()
        assert sse.startswith("event: message\n")
        assert "data: " in sse
        assert sse.endswith("\n\n")
        # Verify the data is valid JSON
        data_line = sse.split("\n")[1]
        json_str = data_line.replace("data: ", "")
        parsed = json.loads(json_str)
        assert parsed["event_type"] == "message"

    def test_thought_factory(self):
        """Test thought event factory."""
        thought = AgentThought(content="Thinking")
        event = AgentExecutionEvent.thought("task-123", thought, sequence=1)
        assert event.event_type == EventType.THOUGHT
        assert event.data["content"] == "Thinking"
        assert event.sequence == 1

    def test_tool_call_factory(self):
        """Test tool call event factory."""
        tool = ToolCallEvent(tool_name="test", arguments={}, call_id="c1")
        event = AgentExecutionEvent.tool_call("task-123", tool)
        assert event.event_type == EventType.TOOL_CALL
        assert event.data["tool_name"] == "test"

    def test_confirmation_factory(self):
        """Test confirmation event factory."""
        request = ConfirmationRequest(call_id="c1", tool_name="test", description="Test?")
        event = AgentExecutionEvent.confirmation("task-123", request)
        assert event.event_type == EventType.CONFIRMATION_REQUEST
        assert event.data["call_id"] == "c1"

    def test_state_change_factory(self):
        """Test state change event factory."""
        event = AgentExecutionEvent.state_change("task-123", "submitted", "working", sequence=2)
        assert event.event_type == EventType.STATE_CHANGE
        assert event.data["old_state"] == "submitted"
        assert event.data["new_state"] == "working"

    def test_message_factory(self):
        """Test message event factory."""
        event = AgentExecutionEvent.message("task-123", "Hello world")
        assert event.event_type == EventType.MESSAGE
        assert event.data["content"] == "Hello world"

    def test_error_factory(self):
        """Test error event factory."""
        event = AgentExecutionEvent.error("task-123", "Something failed", "ERR_001")
        assert event.event_type == EventType.ERROR
        assert event.data["error"] == "Something failed"
        assert event.data["code"] == "ERR_001"

    def test_complete_factory(self):
        """Test complete event factory."""
        event = AgentExecutionEvent.complete("task-123", "All done")
        assert event.event_type == EventType.COMPLETE
        assert event.data["result"] == "All done"
