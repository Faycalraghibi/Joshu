"""
Command Processing System for Joshu CLI.

This package provides standardized command handling with
consistent action return types for agent integration.

Key components:
- types: Command action return types
- handlers: init and restore
"""

from joshu.commands.handlers import (
    GitService,
    RestoreToolCallData,
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
    "GitService",
    "RestoreToolCallData",
]
