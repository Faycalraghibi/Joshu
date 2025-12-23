"""
Hook Schemas.

Defines the data structures for hook communication.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Literal, Optional

from joshu.hooks.events import HookEvent


@dataclass
class HookPayload:
    """
    Payload sent to hook scripts via stdin.

    Contains:
    - event: The hook event type
    - timestamp: When the event occurred
    - session_id: Current session identifier
    - data: Event-specific data
    """

    event: HookEvent
    session_id: str
    data: Dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "event": self.event.value,
            "session_id": self.session_id,
            "timestamp": self.timestamp,
            "data": self.data,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "HookPayload":
        """Create from dictionary."""
        return cls(
            event=HookEvent(data.get("event", "before_agent")),
            session_id=data.get("session_id", ""),
            timestamp=data.get("timestamp", datetime.now().isoformat()),
            data=data.get("data", {}),
        )


@dataclass
class HookResponse:
    """
    Response received from hook scripts via stdout.

    Contains:
    - action: What to do (allow, block, modify)
    - modified_data: Modified data if action is 'modify'
    - message: Optional message from the hook
    """

    action: Literal["allow", "block", "modify"] = "allow"
    modified_data: Optional[Dict[str, Any]] = None
    message: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "action": self.action,
            "modified_data": self.modified_data,
            "message": self.message,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "HookResponse":
        """Create from dictionary."""
        return cls(
            action=data.get("action", "allow"),
            modified_data=data.get("modified_data"),
            message=data.get("message"),
        )


@dataclass
class HookResult:
    """
    Result of executing a hook.

    Contains:
    - success: Whether the hook executed successfully
    - allowed: Whether the action should proceed
    - response: The hook's response (if any)
    - error: Error message (if failed)
    - exit_code: The hook script's exit code
    """

    success: bool = True
    allowed: bool = True
    response: Optional[HookResponse] = None
    error: Optional[str] = None
    exit_code: int = 0

    @property
    def should_block(self) -> bool:
        """Check if the hook wants to block execution."""
        return not self.allowed or (self.response is not None and self.response.action == "block")

    @property
    def modified_data(self) -> Optional[Dict[str, Any]]:
        """Get modified data if available."""
        if self.response and self.response.action == "modify":
            return self.response.modified_data
        return None


# Event-specific payload data types


@dataclass
class SessionStartData:
    """Data for SESSION_START event."""

    workspace_path: str
    config: Dict[str, Any] = field(default_factory=dict)


@dataclass
class BeforeAgentData:
    """Data for BEFORE_AGENT event."""

    prompt: str
    context: str = ""
    conversation_history: list = field(default_factory=list)


@dataclass
class BeforeToolSelectionData:
    """Data for BEFORE_TOOL_SELECTION event."""

    available_tools: list = field(default_factory=list)
    prompt: str = ""


@dataclass
class BeforeToolData:
    """Data for BEFORE_TOOL event."""

    tool_name: str
    arguments: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AfterToolData:
    """Data for AFTER_TOOL event."""

    tool_name: str
    arguments: Dict[str, Any] = field(default_factory=dict)
    result: Any = None
    success: bool = True
    error: Optional[str] = None


@dataclass
class AfterAgentData:
    """Data for AFTER_AGENT event."""

    response: str
    tool_calls: list = field(default_factory=list)
    tokens_used: int = 0


@dataclass
class SessionEndData:
    """Data for SESSION_END event."""

    duration_seconds: float = 0.0
    messages_count: int = 0
    tools_called: list = field(default_factory=list)
