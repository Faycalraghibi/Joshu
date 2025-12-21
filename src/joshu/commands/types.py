"""
Command action return types for CLI command processing.

This module defines standardized return types for command actions,
enabling consistent communication between commands and the agent.

Key principles:
- ZERO execution logic - defines data structures only
- Standardized action types for all commands
- Supports tool calls, messages, history loading, prompt submission
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class CommandActionType(Enum):
    """Types of actions a command can return."""

    TOOL_CALL = "tool_call"  # Schedule a tool call
    MESSAGE = "message"  # Display message to user
    LOAD_HISTORY = "load_history"  # Load conversation history
    SUBMIT_PROMPT = "submit_prompt"  # Submit prompt to LLM
    ERROR = "error"  # Report an error
    SUCCESS = "success"  # Report success
    NO_OP = "no_op"  # No action needed


@dataclass
class CommandActionReturn:
    """
    Base class for command action returns.

    All command actions inherit from this to provide
    consistent typing and serialization.

    Attributes:
        action_type: Type of action to take
        metadata: Additional action context
    """

    # Use default value to allow subclass dataclasses to work properly
    action_type: CommandActionType = CommandActionType.NO_OP
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "action_type": self.action_type.value,
            "metadata": self.metadata,
        }


@dataclass
class ToolActionReturn(CommandActionReturn):
    """
    Action to schedule a tool call.

    Attributes:
        tool_name: Name of tool to execute
        tool_arguments: Arguments for the tool
        requires_approval: Whether user must approve
    """

    tool_name: str = ""
    tool_arguments: Dict[str, Any] = field(default_factory=dict)
    requires_approval: bool = False

    def __post_init__(self) -> None:
        self.action_type = CommandActionType.TOOL_CALL

    def to_dict(self) -> Dict[str, Any]:
        base = super().to_dict()
        base.update(
            {
                "tool_name": self.tool_name,
                "tool_arguments": self.tool_arguments,
                "requires_approval": self.requires_approval,
            }
        )
        return base


@dataclass
class MessageActionReturn(CommandActionReturn):
    """
    Action to display a message to the user.

    Attributes:
        message: Message content
        message_type: Type (info, warning, error, success)
    """

    message: str = ""
    message_type: str = "info"

    def __post_init__(self) -> None:
        self.action_type = CommandActionType.MESSAGE

    def to_dict(self) -> Dict[str, Any]:
        base = super().to_dict()
        base.update(
            {
                "message": self.message,
                "message_type": self.message_type,
            }
        )
        return base


@dataclass
class LoadHistoryActionReturn(CommandActionReturn):
    """
    Action to load/replace conversation history.

    Attributes:
        history: Messages to load
        client_history: Client-specific history data
        replace_existing: Whether to replace or append
    """

    history: List[Dict[str, Any]] = field(default_factory=list)
    client_history: List[Dict[str, Any]] = field(default_factory=list)
    replace_existing: bool = True

    def __post_init__(self) -> None:
        self.action_type = CommandActionType.LOAD_HISTORY

    def to_dict(self) -> Dict[str, Any]:
        base = super().to_dict()
        base.update(
            {
                "history": self.history,
                "client_history": self.client_history,
                "replace_existing": self.replace_existing,
            }
        )
        return base


@dataclass
class SubmitPromptActionReturn(CommandActionReturn):
    """
    Action to submit a prompt to the LLM.

    Used for commands that need to trigger AI generation.

    Attributes:
        prompt: Prompt text to submit
        system_instruction: Optional system instruction override
        include_context: Whether to include current context
    """

    prompt: str = ""
    system_instruction: Optional[str] = None
    include_context: bool = True

    def __post_init__(self) -> None:
        self.action_type = CommandActionType.SUBMIT_PROMPT

    def to_dict(self) -> Dict[str, Any]:
        base = super().to_dict()
        base.update(
            {
                "prompt": self.prompt,
                "system_instruction": self.system_instruction,
                "include_context": self.include_context,
            }
        )
        return base


@dataclass
class ErrorActionReturn(CommandActionReturn):
    """
    Action to report an error.

    Attributes:
        error_message: Error description
        error_code: Optional error code
        recoverable: Whether the error is recoverable
    """

    error_message: str = ""
    error_code: Optional[str] = None
    recoverable: bool = True

    def __post_init__(self) -> None:
        self.action_type = CommandActionType.ERROR

    def to_dict(self) -> Dict[str, Any]:
        base = super().to_dict()
        base.update(
            {
                "error_message": self.error_message,
                "error_code": self.error_code,
                "recoverable": self.recoverable,
            }
        )
        return base


@dataclass
class SuccessActionReturn(CommandActionReturn):
    """
    Action to report success.

    Attributes:
        message: Success message
        result: Optional result data
    """

    message: str = ""
    result: Optional[Any] = None

    def __post_init__(self) -> None:
        self.action_type = CommandActionType.SUCCESS


@dataclass
class NoOpActionReturn(CommandActionReturn):
    """
    Action indicating no action is needed.

    Attributes:
        reason: Why no action is needed
    """

    reason: str = ""

    def __post_init__(self) -> None:
        self.action_type = CommandActionType.NO_OP
