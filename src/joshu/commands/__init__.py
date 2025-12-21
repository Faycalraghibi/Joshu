"""
Command Processing System for Joshu CLI.

This package provides standardized command handling with
consistent action return types for agent integration.

Key components:
- types: Command action return types
- handlers: Init, restore, and extension commands
"""

from joshu.commands.handlers import (
    GitService,
    RestoreToolCallData,
    list_extensions,
    perform_init,
    perform_restore,
)
from joshu.commands.types import (
    CommandActionReturn,
    CommandActionType,
    ErrorActionReturn,
    LoadHistoryActionReturn,
    MessageActionReturn,
    NoOpActionReturn,
    SubmitPromptActionReturn,
    SuccessActionReturn,
    ToolActionReturn,
)

__all__ = [
    # Types
    "CommandActionReturn",
    "CommandActionType",
    "ToolActionReturn",
    "MessageActionReturn",
    "LoadHistoryActionReturn",
    "SubmitPromptActionReturn",
    "ErrorActionReturn",
    "SuccessActionReturn",
    "NoOpActionReturn",
    # Handlers
    "perform_init",
    "perform_restore",
    "list_extensions",
    "GitService",
    "RestoreToolCallData",
]
