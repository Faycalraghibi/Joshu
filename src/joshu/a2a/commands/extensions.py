"""
Extensions command for managing Joshu extensions.

NOTE: This module provides transport and orchestration only.
It must not introduce new agent logic or execution semantics.
"""

from __future__ import annotations

import logging
from typing import Any, AsyncIterator, Dict

from joshu.a2a.commands.types import (
    BaseCommand,
    CommandContext,
    CommandResult,
)
from joshu.commands.handlers import list_extensions
from joshu.commands.types import MessageActionReturn

logger = logging.getLogger(__name__)


class ListExtensionsCommand(BaseCommand):
    """List all configured extensions."""

    def __init__(self) -> None:
        super().__init__(
            _name="list",
            _description="List all configured extensions",
            _arguments=[],
        )

    async def execute(
        self, ctx: CommandContext, args: Dict[str, Any]
    ) -> AsyncIterator[CommandResult]:
        """List configured extensions."""
        # Use existing handler
        result = list_extensions(ctx.config)

        if isinstance(result, MessageActionReturn):
            extensions = result.metadata.get("extensions", [])
            yield CommandResult.success(
                message=result.message,
                data={"extensions": extensions, "count": len(extensions)},
            )
        else:
            yield CommandResult.success(message="No extensions configured")


class ExtensionsCommand(BaseCommand):
    """
    Manage Joshu extensions.

    Provides subcommands for listing and managing extensions.
    Default action (no subcommand) lists all extensions.
    """

    def __init__(self) -> None:
        super().__init__(
            _name="extensions",
            _description="Manage Joshu extensions",
            _arguments=[],
            _subcommands=[ListExtensionsCommand()],
        )

    async def execute(
        self, ctx: CommandContext, args: Dict[str, Any]
    ) -> AsyncIterator[CommandResult]:
        """
        Execute extensions command.

        Default action is to list extensions.
        """
        # Check for subcommand
        subcommand = args.get("subcommand")
        if subcommand:
            for sub in self.subcommands:
                if sub.name == subcommand:
                    async for result in sub.execute(ctx, args):
                        yield result
                    return

        # Default: list extensions
        list_cmd = self.subcommands[0]  # ListExtensionsCommand
        async for result in list_cmd.execute(ctx, args):
            yield result
