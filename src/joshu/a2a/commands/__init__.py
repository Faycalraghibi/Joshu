"""
A2A Commands package for CLI command management.

Provides command registry, types, and built-in commands for
the A2A server.

NOTE: This module provides transport and orchestration only.
It must not introduce new agent logic or execution semantics.
"""

from joshu.a2a.commands.registry import CommandRegistry, get_command_registry
from joshu.a2a.commands.types import (
    Command,
    CommandArgument,
    CommandContext,
    CommandResult,
)

__all__ = [
    "Command",
    "CommandArgument",
    "CommandContext",
    "CommandResult",
    "CommandRegistry",
    "get_command_registry",
]
