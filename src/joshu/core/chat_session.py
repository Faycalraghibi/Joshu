"""
Chat session and history management.

This module provides declarative structures for managing
conversational interactions with LLMs.

Key principles:
- ZERO execution logic - tracks state, does not make LLM calls
- Session lifecycle management
- History with curated/comprehensive modes
- Checkpoint support for persistence
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)


class MessageRole(Enum):
    """Role of a message in the conversation."""

    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


class SessionState(Enum):
    """State of a chat session."""

    INITIALIZED = "initialized"
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    ERROR = "error"


@dataclass
class ChatMessage:
    """
    A single message in a conversation.

    Attributes:
        role: Who sent the message
        content: Message content
        name: Optional name (for tool messages)
        tool_call_id: ID if this is a tool response
        tool_calls: Tool calls made in this message
        timestamp: When the message was created
        metadata: Additional message metadata
    """

    role: MessageRole
    content: str
    name: Optional[str] = None
    tool_call_id: Optional[str] = None
    tool_calls: List[Dict[str, Any]] = field(default_factory=list)
    timestamp: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.timestamp is None:
            self.timestamp = datetime.now()

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API calls."""
        result: Dict[str, Any] = {
            "role": self.role.value,
            "content": self.content,
        }
        if self.name:
            result["name"] = self.name
        if self.tool_call_id:
            result["tool_call_id"] = self.tool_call_id
        if self.tool_calls:
            result["tool_calls"] = self.tool_calls
        return result

    @classmethod
    def system(cls, content: str) -> "ChatMessage":
        """Create a system message."""
        return cls(role=MessageRole.SYSTEM, content=content)

    @classmethod
    def user(cls, content: str) -> "ChatMessage":
        """Create a user message."""
        return cls(role=MessageRole.USER, content=content)

    @classmethod
    def assistant(cls, content: str, tool_calls: Optional[List[Dict]] = None) -> "ChatMessage":
        """Create an assistant message."""
        return cls(
            role=MessageRole.ASSISTANT,
            content=content,
            tool_calls=tool_calls or [],
        )

    @classmethod
    def tool(cls, content: str, tool_call_id: str, name: str) -> "ChatMessage":
        """Create a tool response message."""
        return cls(
            role=MessageRole.TOOL,
            content=content,
            tool_call_id=tool_call_id,
            name=name,
        )


@dataclass
class ChatHistory:
    """
    Manages conversational history.

    Supports curated (summarized) and comprehensive (full) modes.

    Attributes:
        messages: All messages in order
        max_messages: Maximum messages to retain
        curated_messages: Summarized history for context
    """

    messages: List[ChatMessage] = field(default_factory=list)
    max_messages: Optional[int] = None
    curated_messages: List[ChatMessage] = field(default_factory=list)

    def add(self, message: ChatMessage) -> None:
        """Add a message to history."""
        self.messages.append(message)
        if self.max_messages and len(self.messages) > self.max_messages:
            # Remove oldest non-system messages
            self._trim_history()

    def _trim_history(self) -> None:
        """Trim history to max_messages."""
        if not self.max_messages:
            return
        # Keep system messages
        system_msgs = [m for m in self.messages if m.role == MessageRole.SYSTEM]
        other_msgs = [m for m in self.messages if m.role != MessageRole.SYSTEM]
        # Keep most recent
        keep_count = self.max_messages - len(system_msgs)
        self.messages = system_msgs + other_msgs[-keep_count:]

    def get_for_api(self, curated: bool = False) -> List[Dict[str, Any]]:
        """Get messages formatted for API calls."""
        msgs = self.curated_messages if curated else self.messages
        return [m.to_dict() for m in msgs]

    def get_last_n(self, n: int) -> List[ChatMessage]:
        """Get last n messages."""
        return self.messages[-n:]

    def clear(self) -> None:
        """Clear all history."""
        self.messages.clear()
        self.curated_messages.clear()

    def __len__(self) -> int:
        return len(self.messages)


@dataclass
class SessionCheckpoint:
    """
    Checkpoint of a session for persistence.

    Attributes:
        session_id: ID of the session
        tag: Unique checkpoint identifier
        history: Saved history at checkpoint
        metadata: Additional checkpoint data
        created_at: When checkpoint was created
    """

    session_id: str
    tag: str
    history: List[Dict[str, Any]]
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: Optional[datetime] = None

    def __post_init__(self) -> None:
        if self.created_at is None:
            self.created_at = datetime.now()


@dataclass
class ChatSessionConfig:
    """
    Configuration for a chat session.

    Attributes:
        model: Model to use for generation
        system_prompt: System prompt for the session
        temperature: Generation temperature
        max_tokens: Maximum tokens per response
        tools_enabled: Whether tools are available
        compress_on_overflow: Compress chat if context overflows
    """

    model: str
    system_prompt: Optional[str] = None
    temperature: float = 0.7
    max_tokens: Optional[int] = None
    tools_enabled: bool = True
    compress_on_overflow: bool = True


class ChatSession:
    """
    Manages a single chat session.

    Tracks session state, history, and configuration.
    Does NOT make actual LLM calls.

    Attributes:
        session_id: Unique session identifier
        config: Session configuration
        history: Conversation history
        state: Current session state
    """

    def __init__(
        self,
        config: ChatSessionConfig,
        session_id: Optional[str] = None,
    ) -> None:
        self.session_id = session_id or str(uuid4())
        self.config = config
        self.history = ChatHistory()
        self.state = SessionState.INITIALIZED
        self.turn_count = 0
        self.created_at = datetime.now()
        self._checkpoints: Dict[str, SessionCheckpoint] = {}

        # Initialize with system prompt
        if config.system_prompt:
            self.history.add(ChatMessage.system(config.system_prompt))

    def start(self) -> None:
        """Start the session."""
        self.state = SessionState.ACTIVE
        logger.debug(f"Session {self.session_id} started")

    def pause(self) -> None:
        """Pause the session."""
        self.state = SessionState.PAUSED

    def resume(self) -> None:
        """Resume a paused session."""
        if self.state == SessionState.PAUSED:
            self.state = SessionState.ACTIVE

    def complete(self) -> None:
        """Mark session as completed."""
        self.state = SessionState.COMPLETED

    def add_user_message(self, content: str) -> ChatMessage:
        """Add a user message and increment turn."""
        message = ChatMessage.user(content)
        self.history.add(message)
        self.turn_count += 1
        return message

    def add_assistant_message(
        self,
        content: str,
        tool_calls: Optional[List[Dict]] = None,
    ) -> ChatMessage:
        """Add an assistant response."""
        message = ChatMessage.assistant(content, tool_calls)
        self.history.add(message)
        return message

    def add_tool_result(self, content: str, tool_call_id: str, name: str) -> ChatMessage:
        """Add a tool execution result."""
        message = ChatMessage.tool(content, tool_call_id, name)
        self.history.add(message)
        return message

    def get_messages_for_api(self) -> List[Dict[str, Any]]:
        """Get messages formatted for LLM API."""
        return self.history.get_for_api()

    def create_checkpoint(self, tag: str) -> SessionCheckpoint:
        """Create a checkpoint of current state."""
        checkpoint = SessionCheckpoint(
            session_id=self.session_id,
            tag=tag,
            history=self.history.get_for_api(),
            metadata={
                "turn_count": self.turn_count,
                "state": self.state.value,
                "model": self.config.model,
            },
        )
        self._checkpoints[tag] = checkpoint
        return checkpoint

    def restore_checkpoint(self, tag: str) -> bool:
        """Restore from a checkpoint."""
        checkpoint = self._checkpoints.get(tag)
        if not checkpoint:
            return False

        # Clear and restore history
        self.history.clear()
        for msg_dict in checkpoint.history:
            role = MessageRole(msg_dict["role"])
            self.history.add(
                ChatMessage(
                    role=role,
                    content=msg_dict.get("content", ""),
                    tool_calls=msg_dict.get("tool_calls", []),
                )
            )

        self.turn_count = checkpoint.metadata.get("turn_count", 0)
        return True

    def reset(self) -> None:
        """Reset session to initial state."""
        self.history.clear()
        self.turn_count = 0
        self.state = SessionState.INITIALIZED
        if self.config.system_prompt:
            self.history.add(ChatMessage.system(self.config.system_prompt))

    def to_dict(self) -> Dict[str, Any]:
        """Serialize session to dictionary."""
        return {
            "session_id": self.session_id,
            "state": self.state.value,
            "turn_count": self.turn_count,
            "model": self.config.model,
            "history_length": len(self.history),
            "created_at": self.created_at.isoformat(),
        }
