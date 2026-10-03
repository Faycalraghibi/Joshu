"""
Unit tests for chat session and tool scheduler.

Run with: pytest tests/core/test_llm_client.py -v
"""

import pytest

from joshu.core.chat_session import (
    ChatHistory,
    ChatMessage,
    ChatSession,
    ChatSessionConfig,
    MessageRole,
    SessionState,
)
from joshu.core.tool_scheduler import (
    ApprovalMode,
    CoreToolScheduler,
    ScheduledToolCall,
    ToolCallStatus,
    ToolSchedulerConfig,
)


class TestChatMessage:
    """Test ChatMessage data structure."""

    def test_create_user_message(self):
        """Test creating user message."""
        msg = ChatMessage.user("Hello")
        assert msg.role == MessageRole.USER
        assert msg.content == "Hello"

    def test_create_tool_message(self):
        """Test creating tool response."""
        msg = ChatMessage.tool("Result", "call_123", "web_search")
        assert msg.role == MessageRole.TOOL
        assert msg.tool_call_id == "call_123"
        assert msg.name == "web_search"

    def test_to_dict(self):
        """Test serialization."""
        msg = ChatMessage.assistant("Hi there")
        data = msg.to_dict()
        assert data["role"] == "assistant"
        assert data["content"] == "Hi there"


class TestChatHistory:
    """Test ChatHistory management."""

    def test_add_message(self):
        """Test adding messages."""
        history = ChatHistory()
        history.add(ChatMessage.user("Hello"))
        history.add(ChatMessage.assistant("Hi"))

        assert len(history) == 2

    def test_trim_history(self):
        """Test history trimming."""
        history = ChatHistory(max_messages=3)
        history.add(ChatMessage.system("System prompt"))
        history.add(ChatMessage.user("1"))
        history.add(ChatMessage.user("2"))
        history.add(ChatMessage.user("3"))

        # Should keep system + last 2 user messages
        assert len(history) == 3


class TestChatSession:
    """Test ChatSession lifecycle."""

    @pytest.fixture
    def session(self):
        config = ChatSessionConfig(
            model="gpt-4o",
            system_prompt="You are a helpful assistant.",
        )
        return ChatSession(config)

    def test_initialization(self, session):
        """Test session initializes correctly."""
        assert session.state == SessionState.INITIALIZED
        assert len(session.history) == 1  # System prompt

    def test_start_session(self, session):
        """Test starting session."""
        session.start()
        assert session.state == SessionState.ACTIVE

    def test_add_messages(self, session):
        """Test adding messages to session."""
        session.start()
        session.add_user_message("Hello")
        session.add_assistant_message("Hi there!")

        assert len(session.history) == 3  # System + user + assistant
        assert session.turn_count == 1

    def test_checkpoint_restore(self, session):
        """Test checkpointing and restore."""
        session.start()
        session.add_user_message("Message 1")
        session.create_checkpoint("v1")

        session.add_user_message("Message 2")
        session.add_user_message("Message 3")

        assert session.turn_count == 3

        # Restore
        session.restore_checkpoint("v1")
        assert session.turn_count == 1


class TestScheduledToolCall:
    """Test ScheduledToolCall data structure."""

    def test_create_call(self):
        """Test creating a tool call."""
        call = ScheduledToolCall(
            call_id="test-123",
            tool_name="web_search",
            arguments={"query": "AI"},
        )
        assert call.status == ToolCallStatus.PENDING

    def test_mark_completed(self):
        """Test marking as completed."""
        call = ScheduledToolCall(
            call_id="test",
            tool_name="test",
            arguments={},
        )
        call.mark_completed("Success!")
        assert call.status == ToolCallStatus.COMPLETED
        assert call.result == "Success!"


class TestCoreToolScheduler:
    """Test CoreToolScheduler functionality."""

    @pytest.fixture
    def scheduler(self):
        config = ToolSchedulerConfig(
            approval_mode=ApprovalMode.SAFE_ONLY,
            safe_tools=["read_file"],
        )
        return CoreToolScheduler(config)

    def test_schedule_safe_tool(self, scheduler):
        """Test scheduling a safe tool auto-approves."""
        call = scheduler.schedule("read_file", {"path": "/test"})
        assert call.status == ToolCallStatus.APPROVED

    def test_schedule_unsafe_tool(self, scheduler):
        """Test scheduling unsafe tool needs approval."""
        call = scheduler.schedule("delete_file", {"path": "/test"})
        assert call.status == ToolCallStatus.PENDING
        assert call.requires_approval is True

    def test_approve_call(self, scheduler):
        """Test manual approval."""
        call = scheduler.schedule("dangerous_tool", {})
        scheduler.approve(call.call_id)
        assert call.status == ToolCallStatus.APPROVED

    def test_reject_call(self, scheduler):
        """Test rejection."""
        call = scheduler.schedule("dangerous_tool", {})
        scheduler.reject(call.call_id, "Too risky")
        assert call.status == ToolCallStatus.REJECTED
        assert call.error == "Too risky"

    def test_get_pending(self, scheduler):
        """Test getting pending calls."""
        scheduler.schedule("tool1", {})
        scheduler.schedule("tool2", {})

        pending = scheduler.get_pending()
        assert len(pending) == 2

    def test_truncate_output(self, scheduler):
        """Test output truncation."""
        scheduler.config.max_output_display = 50
        long_output = "A" * 100

        truncated = scheduler.truncate_output(long_output)
        assert len(truncated) < 100
        assert "truncated" in truncated
