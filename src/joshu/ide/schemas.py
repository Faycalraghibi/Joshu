"""
IDE Integration Schemas.

Defines data structures for IDE context and communication.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class CursorPosition:
    """Cursor position in a file."""

    line: int
    column: int


@dataclass
class FileInfo:
    """Information about an open file."""

    path: str
    language: str = ""
    is_active: bool = False


@dataclass
class IdeContext:
    """
    Context from the IDE.

    Provides information about the user's current editor state.
    """

    # Workspace information
    workspace_path: str = ""

    # Open files (most recent first)
    recent_files: List[FileInfo] = field(default_factory=list)

    # Active file information
    active_file: Optional[str] = None
    cursor_position: Optional[CursorPosition] = None

    # Selected text (limited to prevent excessive data)
    selected_text: str = ""

    # IDE metadata
    ide_type: str = "vscode"
    ide_version: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "workspace_path": self.workspace_path,
            "recent_files": [
                {"path": f.path, "language": f.language, "is_active": f.is_active}
                for f in self.recent_files
            ],
            "active_file": self.active_file,
            "cursor_position": (
                {"line": self.cursor_position.line, "column": self.cursor_position.column}
                if self.cursor_position
                else None
            ),
            "selected_text": self.selected_text,
            "ide_type": self.ide_type,
            "ide_version": self.ide_version,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "IdeContext":
        """Create from dictionary."""
        cursor = data.get("cursor_position")
        return cls(
            workspace_path=data.get("workspace_path", ""),
            recent_files=[
                FileInfo(
                    path=f.get("path", ""),
                    language=f.get("language", ""),
                    is_active=f.get("is_active", False),
                )
                for f in data.get("recent_files", [])
            ],
            active_file=data.get("active_file"),
            cursor_position=(
                CursorPosition(line=cursor["line"], column=cursor["column"]) if cursor else None
            ),
            selected_text=data.get("selected_text", ""),
            ide_type=data.get("ide_type", "vscode"),
            ide_version=data.get("ide_version", ""),
        )


@dataclass
class DiffProposal:
    """
    A proposed file modification.

    Sent from CLI to IDE for native diff display.
    """

    file_path: str
    original_content: str
    proposed_content: str
    description: str = ""
    proposal_id: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "file_path": self.file_path,
            "original_content": self.original_content,
            "proposed_content": self.proposed_content,
            "description": self.description,
            "proposal_id": self.proposal_id,
        }


@dataclass
class DiffAction:
    """
    User action on a diff proposal.

    Sent from IDE to CLI after user decision.
    """

    proposal_id: str
    action: str  # "accept", "reject", "edit"
    edited_content: Optional[str] = None  # If action is "edit"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "proposal_id": self.proposal_id,
            "action": self.action,
            "edited_content": self.edited_content,
        }
