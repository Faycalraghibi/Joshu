"""
Command handlers for project initialization and restoration.

This module provides command handlers for init and restore operations,
producing CommandActionReturn results for the agent to process.

Key principles:
- ZERO execution logic - returns actions, does not execute them
- Support for GEMINI.md initialization
- Checkpoint restoration with Git integration
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Generator, List, Optional

from joshu.commands.types import (
    CommandActionReturn,
    ErrorActionReturn,
    LoadHistoryActionReturn,
    MessageActionReturn,
    NoOpActionReturn,
    SubmitPromptActionReturn,
)

logger = logging.getLogger(__name__)


# Project descriptor filename
PROJECT_DESCRIPTOR = "GEMINI.md"


@dataclass
class GitService:
    """
    Interface for Git operations.

    This is a stub interface - actual Git operations
    would be implemented by the caller.

    Attributes:
        project_root: Root directory of the project
    """

    project_root: Path

    def get_current_commit(self) -> Optional[str]:
        """Get current commit hash."""
        # Stub - actual implementation would call git
        return None

    def checkout_commit(self, commit_hash: str) -> bool:
        """Checkout a specific commit."""
        # Stub - actual implementation would call git
        return False

    def has_uncommitted_changes(self) -> bool:
        """Check for uncommitted changes."""
        # Stub
        return False


@dataclass
class RestoreToolCallData:
    """
    Data for restore command tool call.

    Attributes:
        checkpoint_tag: Tag of checkpoint to restore
        history: Conversation history to restore
        client_history: Client-specific history
        commit_hash: Optional Git commit to restore to
    """

    checkpoint_tag: str
    history: List[Dict[str, Any]]
    client_history: List[Dict[str, Any]]
    commit_hash: Optional[str] = None


def perform_init(
    project_dir: Path,
    does_gemini_md_exist: Optional[bool] = None,
) -> CommandActionReturn:
    """
    Perform project initialization.

    If GEMINI.md exists, returns NoOp.
    If not, returns SubmitPromptAction to generate it.

    Args:
        project_dir: Project directory path
        does_gemini_md_exist: Override for existence check

    Returns:
        CommandActionReturn with appropriate action
    """
    # Check if GEMINI.md exists
    gemini_path = project_dir / PROJECT_DESCRIPTOR
    exists = does_gemini_md_exist if does_gemini_md_exist is not None else gemini_path.exists()

    if exists:
        logger.debug(f"{PROJECT_DESCRIPTOR} already exists in {project_dir}")
        return NoOpActionReturn(
            reason=f"{PROJECT_DESCRIPTOR} already exists",
            metadata={"path": str(gemini_path)},
        )

    # Generate prompt for AI to create GEMINI.md
    prompt = _generate_init_prompt(project_dir)

    logger.info(f"Generating {PROJECT_DESCRIPTOR} for {project_dir}")
    return SubmitPromptActionReturn(
        prompt=prompt,
        system_instruction=_get_init_system_instruction(),
        include_context=True,
        metadata={
            "project_dir": str(project_dir),
            "target_file": str(gemini_path),
        },
    )


def _generate_init_prompt(project_dir: Path) -> str:
    """Generate prompt for GEMINI.md creation."""
    return f"""Analyze the current directory and create a GEMINI.md project descriptor file.

The directory is: {project_dir}

Your task:
1. Examine the project structure and files
2. Determine the project type (code repository, documentation, etc.)
3. Identify the primary programming languages and frameworks
4. Generate appropriate GEMINI.md content including:
   - Project overview
   - Key components and architecture
   - Development guidelines
   - Relevant context for AI assistance

Create the GEMINI.md file with this information."""


def _get_init_system_instruction() -> str:
    """Get system instruction for init command."""
    return """You are initializing a project for AI-assisted development.
Analyze the project structure carefully and create a comprehensive
GEMINI.md file that will help future AI interactions understand
the project context, coding conventions, and key components."""


def perform_restore(
    tool_call_data: RestoreToolCallData,
    git_service: Optional[GitService] = None,
) -> Generator[CommandActionReturn, None, None]:
    """
    Perform state restoration from checkpoint.

    This is a generator that yields CommandActionReturn objects
    for each step of the restoration process.

    Args:
        tool_call_data: Restoration data including history
        git_service: Optional Git service for file restoration

    Yields:
        CommandActionReturn for each restoration step
    """
    # Step 1: Notify start
    yield MessageActionReturn(
        message=f"Restoring from checkpoint: {tool_call_data.checkpoint_tag}",
        message_type="info",
    )

    # Step 2: Restore Git state if commit hash provided
    if tool_call_data.commit_hash and git_service:
        logger.info(f"Restoring to Git commit: {tool_call_data.commit_hash}")

        # Check for uncommitted changes
        if git_service.has_uncommitted_changes():
            yield MessageActionReturn(
                message="Warning: Uncommitted changes detected",
                message_type="warning",
            )

        # Attempt checkout
        success = git_service.checkout_commit(tool_call_data.commit_hash)
        if not success:
            yield ErrorActionReturn(
                error_message=f"Failed to checkout commit: {tool_call_data.commit_hash}",
                error_code="GIT_CHECKOUT_FAILED",
                recoverable=True,
            )
        else:
            yield MessageActionReturn(
                message=f"Restored project files to commit: {tool_call_data.commit_hash[:8]}",
                message_type="success",
            )

    # Step 3: Restore conversation history
    if tool_call_data.history:
        logger.info(f"Restoring {len(tool_call_data.history)} history messages")
        yield LoadHistoryActionReturn(
            history=tool_call_data.history,
            client_history=tool_call_data.client_history,
            replace_existing=True,
            metadata={"checkpoint_tag": tool_call_data.checkpoint_tag},
        )

    # Step 4: Final success message
    yield MessageActionReturn(
        message=f"Restoration complete: {tool_call_data.checkpoint_tag}",
        message_type="success",
    )
