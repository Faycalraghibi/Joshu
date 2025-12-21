"""
Restore command for checkpoint management.

Provides commands for restoring from checkpoints and listing
available checkpoints.

NOTE: This module provides transport and orchestration only.
It must not introduce new agent logic or execution semantics.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, AsyncIterator, Dict, Optional

from joshu.a2a.commands.types import (
    BaseCommand,
    CommandArgument,
    CommandContext,
    CommandResult,
)
from joshu.a2a.events import AgentExecutionEvent
from joshu.commands.handlers import RestoreToolCallData, perform_restore
from joshu.commands.types import (
    ErrorActionReturn,
    LoadHistoryActionReturn,
    MessageActionReturn,
)

logger = logging.getLogger(__name__)


# Default checkpoint directory name
CHECKPOINT_DIR = ".joshu_checkpoints"


class ListCheckpointsCommand(BaseCommand):
    """List available checkpoints in the project."""

    def __init__(self) -> None:
        super().__init__(
            _name="list",
            _description="List available checkpoints",
            _arguments=[
                CommandArgument(
                    name="directory",
                    description="Project directory to search",
                    required=False,
                    default=".",
                ),
            ],
        )

    async def execute(
        self, ctx: CommandContext, args: Dict[str, Any]
    ) -> AsyncIterator[CommandResult]:
        """List available checkpoints."""
        # Determine checkpoint directory
        directory = args.get("directory", ".")
        if directory == ".":
            checkpoint_dir = ctx.workspace_path / CHECKPOINT_DIR
        else:
            checkpoint_dir = Path(directory) / CHECKPOINT_DIR

        if not checkpoint_dir.exists():
            yield CommandResult.success(
                message="No checkpoints directory found",
                data={"checkpoints": [], "count": 0},
            )
            return

        # Find checkpoint files
        checkpoints = []
        for checkpoint_file in checkpoint_dir.glob("*.json"):
            try:
                with open(checkpoint_file) as f:
                    data = json.load(f)
                    checkpoints.append(
                        {
                            "tag": checkpoint_file.stem,
                            "path": str(checkpoint_file),
                            "created_at": data.get("created_at"),
                            "message_count": len(data.get("history", [])),
                        }
                    )
            except (json.JSONDecodeError, IOError) as e:
                logger.warning(f"Failed to read checkpoint {checkpoint_file}: {e}")

        yield CommandResult.success(
            message=f"Found {len(checkpoints)} checkpoint(s)",
            data={"checkpoints": checkpoints, "count": len(checkpoints)},
        )


class RestoreCommand(BaseCommand):
    """
    Restore from a checkpoint.

    Restores conversation history and optionally Git state
    from a checkpoint file.
    """

    def __init__(self) -> None:
        super().__init__(
            _name="restore",
            _description="Restore from a checkpoint",
            _arguments=[
                CommandArgument(
                    name="checkpoint",
                    description="Checkpoint tag or file path",
                    required=True,
                ),
                CommandArgument(
                    name="restore_files",
                    description="Whether to restore Git state",
                    arg_type="boolean",
                    required=False,
                    default=False,
                ),
            ],
            _subcommands=[ListCheckpointsCommand()],
        )

    async def execute(
        self, ctx: CommandContext, args: Dict[str, Any]
    ) -> AsyncIterator[CommandResult]:
        """Execute checkpoint restoration."""
        # Check for subcommand
        subcommand = args.get("subcommand")
        if subcommand == "list":
            list_cmd = self.subcommands[0]
            async for result in list_cmd.execute(ctx, args):
                yield result
            return

        # Get checkpoint path
        checkpoint = args.get("checkpoint")
        if not checkpoint:
            yield CommandResult.make_error("Checkpoint tag or path required")
            return

        # Resolve checkpoint path
        checkpoint_path = self._resolve_checkpoint_path(ctx.workspace_path, checkpoint)
        if not checkpoint_path or not checkpoint_path.exists():
            yield CommandResult.make_error(f"Checkpoint not found: {checkpoint}")
            return

        # Load checkpoint data
        try:
            with open(checkpoint_path) as f:
                checkpoint_data = json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            yield CommandResult.make_error(f"Failed to read checkpoint: {e}")
            return

        # Create restoration data
        tool_call_data = RestoreToolCallData(
            checkpoint_tag=checkpoint_path.stem,
            history=checkpoint_data.get("history", []),
            client_history=checkpoint_data.get("client_history", []),
            commit_hash=checkpoint_data.get("commit_hash") if args.get("restore_files") else None,
        )

        # Use existing restore handler (generator)
        for action in perform_restore(tool_call_data, ctx.git_service):
            # Publish event if event bus available
            if ctx.event_bus and ctx.task_id:
                if isinstance(action, MessageActionReturn):
                    event = AgentExecutionEvent.message(ctx.task_id, action.message)
                    await ctx.event_bus.publish(event)

            # Yield result based on action type
            if isinstance(action, MessageActionReturn):
                yield CommandResult.success(
                    message=action.message,
                    data={"type": action.message_type},
                )
            elif isinstance(action, ErrorActionReturn):
                yield CommandResult.make_error(
                    error_msg=action.error_message,
                    message=action.error_code or "",
                )
            elif isinstance(action, LoadHistoryActionReturn):
                yield CommandResult.success(
                    message=f"Loaded {len(action.history)} history messages",
                    data={
                        "history_count": len(action.history),
                        "checkpoint_tag": action.metadata.get("checkpoint_tag"),
                    },
                )

    def _resolve_checkpoint_path(self, workspace: Path, checkpoint: str) -> Optional[Path]:
        """Resolve checkpoint tag or path to actual file path."""
        # Check if it's a direct path
        path = Path(checkpoint)
        if path.exists():
            return path

        # Check in checkpoint directory
        checkpoint_dir = workspace / CHECKPOINT_DIR
        checkpoint_file = checkpoint_dir / f"{checkpoint}.json"
        if checkpoint_file.exists():
            return checkpoint_file

        return None
