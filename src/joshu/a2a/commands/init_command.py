"""
Init command for project initialization.

Wraps existing perform_init for A2A, publishing events to EventBus.

NOTE: This module provides transport and orchestration only.
It must not introduce new agent logic or execution semantics.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, AsyncIterator, Dict

from joshu.a2a.commands.types import (
    BaseCommand,
    CommandArgument,
    CommandContext,
    CommandResult,
    CommandStatus,
)
from joshu.a2a.events import AgentExecutionEvent
from joshu.commands.handlers import perform_init
from joshu.commands.types import (
    NoOpActionReturn,
    SubmitPromptActionReturn,
)

logger = logging.getLogger(__name__)


class InitCommand(BaseCommand):
    """
    Initialize a project with GEMINI.md.

    Analyzes the project structure and generates a GEMINI.md
    descriptor file for AI-assisted development.
    """

    def __init__(self) -> None:
        super().__init__(
            _name="init",
            _description="Initialize project with GEMINI.md descriptor",
            _arguments=[
                CommandArgument(
                    name="directory",
                    description="Project directory to initialize",
                    arg_type="string",
                    required=False,
                    default=".",
                ),
            ],
        )

    async def execute(
        self, ctx: CommandContext, args: Dict[str, Any]
    ) -> AsyncIterator[CommandResult]:
        """
        Execute project initialization.

        Uses existing perform_init handler and streams updates
        via the event bus.
        """
        # Determine project directory
        directory = args.get("directory", ".")
        if directory == ".":
            project_dir = ctx.workspace_path
        else:
            project_dir = Path(directory)

        logger.info(f"Initializing project in {project_dir}")

        # Publish start event
        if ctx.event_bus and ctx.task_id:
            event = AgentExecutionEvent.message(
                ctx.task_id,
                f"Initializing project: {project_dir}",
            )
            await ctx.event_bus.publish(event)

        # Use existing handler
        result = perform_init(project_dir)

        # Handle based on action type
        if isinstance(result, NoOpActionReturn):
            # GEMINI.md already exists
            yield CommandResult.success(
                message=f"Project already initialized: {result.metadata.get('path', '')}",
                data={"already_exists": True, "path": str(result.metadata.get("path", ""))},
            )

        elif isinstance(result, SubmitPromptActionReturn):
            # Need to submit prompt to agent
            if ctx.event_bus and ctx.task_id:
                event = AgentExecutionEvent.message(
                    ctx.task_id,
                    "Generating GEMINI.md content...",
                )
                await ctx.event_bus.publish(event)

            # Submit to executor if available
            if ctx.executor:
                # Create a sub-task for the prompt
                # The executor will handle the actual LLM interaction
                yield CommandResult(
                    status=CommandStatus.REQUIRES_INPUT,
                    message="Submitting prompt to generate GEMINI.md",
                    data={
                        "prompt": result.prompt,
                        "system_instruction": result.system_instruction,
                        "target_file": result.metadata.get("target_file", ""),
                    },
                )
            else:
                yield CommandResult.success(
                    message="Ready to generate GEMINI.md",
                    data={
                        "prompt": result.prompt,
                        "target_file": result.metadata.get("target_file", ""),
                    },
                )

        else:
            yield CommandResult.make_error(f"Unexpected result type: {type(result)}")
