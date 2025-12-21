"""
A2A Command types and protocols.

Defines the Command protocol, CommandContext, and related types
for the A2A command system.

NOTE: This module provides transport and orchestration only.
It must not introduce new agent logic or execution semantics.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import (
    TYPE_CHECKING,
    Any,
    AsyncIterator,
    Dict,
    List,
    Optional,
    Protocol,
    runtime_checkable,
)

if TYPE_CHECKING:
    from joshu.a2a.event_bus import ExecutionEventBus
    from joshu.a2a.executor import AgentExecutor
    from joshu.commands.handlers import GitService

logger = logging.getLogger(__name__)


class CommandStatus(Enum):
    """Status of command execution."""

    SUCCESS = "success"
    ERROR = "error"
    PENDING = "pending"
    REQUIRES_INPUT = "requires_input"


@dataclass
class CommandArgument:
    """
    Definition of a command argument.

    Attributes:
        name: Argument name
        description: Human-readable description
        arg_type: Type of argument (string, int, bool, etc.)
        required: Whether argument is required
        default: Default value if not provided
    """

    name: str
    description: str
    arg_type: str = "string"
    required: bool = False
    default: Any = None

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "name": self.name,
            "description": self.description,
            "type": self.arg_type,
            "required": self.required,
            "default": self.default,
        }


@dataclass
class CommandResult:
    """
    Result of command execution.

    Attributes:
        status: Execution status
        message: Human-readable result message
        data: Optional result data
        error_message: Error message if failed
    """

    status: CommandStatus
    message: str = ""
    data: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "status": self.status.value,
            "message": self.message,
            "data": self.data,
            "error": self.error_message,
        }

    @classmethod
    def success(cls, message: str = "", data: Optional[Dict[str, Any]] = None) -> "CommandResult":
        """Create success result."""
        return cls(status=CommandStatus.SUCCESS, message=message, data=data)

    @classmethod
    def make_error(cls, error_msg: str, message: str = "") -> "CommandResult":
        """Create error result."""
        return cls(status=CommandStatus.ERROR, message=message, error_message=error_msg)


@dataclass
class CommandContext:
    """
    Context provided to commands during execution.

    Contains services and configuration needed for command execution.

    Attributes:
        workspace_path: Working directory for the command
        config: Application configuration
        event_bus: Event bus for publishing updates
        executor: Agent executor for submitting prompts
        git_service: Optional Git service for version control
        task_id: Optional task ID for tracking
    """

    workspace_path: Path
    config: Dict[str, Any] = field(default_factory=dict)
    event_bus: Optional["ExecutionEventBus"] = None
    executor: Optional["AgentExecutor"] = None
    git_service: Optional["GitService"] = None
    task_id: Optional[str] = None

    def get_config(self, key: str, default: Any = None) -> Any:
        """Get a configuration value."""
        return self.config.get(key, default)


@runtime_checkable
class Command(Protocol):
    """
    Protocol for A2A commands.

    Commands are executable units that can be registered with
    the CommandRegistry and invoked via the HTTP API.

    Attributes:
        name: Command name (used for invocation)
        description: Human-readable description
        arguments: List of command arguments
        subcommands: List of nested subcommands
    """

    @property
    def name(self) -> str:
        """Command name."""
        ...

    @property
    def description(self) -> str:
        """Human-readable description."""
        ...

    @property
    def arguments(self) -> List[CommandArgument]:
        """Command arguments."""
        ...

    @property
    def subcommands(self) -> List["Command"]:
        """Nested subcommands."""
        ...

    def execute(self, ctx: CommandContext, args: Dict[str, Any]) -> AsyncIterator[CommandResult]:
        """
        Execute the command.

        Args:
            ctx: Execution context
            args: Command arguments

        Yields:
            CommandResult for each step of execution
        """
        ...


@dataclass
class BaseCommand:
    """
    Base implementation of Command protocol.

    Provides default implementations for common functionality.
    Subclass and override execute() to implement command logic.
    """

    _name: str
    _description: str
    _arguments: List[CommandArgument] = field(default_factory=list)
    _subcommands: List["BaseCommand"] = field(default_factory=list)

    @property
    def name(self) -> str:
        return self._name

    @property
    def description(self) -> str:
        return self._description

    @property
    def arguments(self) -> List[CommandArgument]:
        return self._arguments

    @property
    def subcommands(self) -> List["BaseCommand"]:
        return self._subcommands

    def add_subcommand(self, cmd: "BaseCommand") -> None:
        """Add a subcommand."""
        self._subcommands.append(cmd)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize command for API response."""
        return {
            "name": self.name,
            "description": self.description,
            "arguments": [arg.to_dict() for arg in self.arguments],
            "subcommands": [
                {"name": sub.name, "description": sub.description} for sub in self.subcommands
            ],
        }

    async def execute(
        self, ctx: CommandContext, args: Dict[str, Any]
    ) -> AsyncIterator[CommandResult]:
        """Default implementation - override in subclasses."""
        yield CommandResult.make_error("Command not implemented")
