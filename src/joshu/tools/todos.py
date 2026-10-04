"""
Todo Management Tool for Joshu CLI.

Enables the agent to break down complex tasks into subtasks,
track their status, and provide transparency into the workflow.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from joshu.core.tool_registry import register_tool

logger = logging.getLogger(__name__)


class TodoStatus(str, Enum):
    """Status values for todo items."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


@dataclass
class TodoItem:
    """Represents a single todo item."""

    description: str
    status: TodoStatus = TodoStatus.PENDING
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "description": self.description,
            "status": self.status.value,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TodoItem":
        """Create from dictionary."""
        status = data.get("status", "pending")
        if isinstance(status, str):
            status = TodoStatus(status)
        return cls(
            description=data.get("description", ""),
            status=status,
            created_at=data.get("created_at", datetime.now().isoformat()),
            updated_at=data.get("updated_at"),
        )


@dataclass
class TodoList:
    """Container for todo items with session tracking."""

    session_id: str
    task_name: str
    items: List[TodoItem] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "session_id": self.session_id,
            "task_name": self.task_name,
            "items": [item.to_dict() for item in self.items],
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TodoList":
        """Create from dictionary."""
        items = [TodoItem.from_dict(item) for item in data.get("items", [])]
        return cls(
            session_id=data.get("session_id", ""),
            task_name=data.get("task_name", ""),
            items=items,
            created_at=data.get("created_at", datetime.now().isoformat()),
        )


# Session-level todo list storage
_current_todos: Optional[TodoList] = None


def get_current_todos() -> Optional[TodoList]:
    """Get the current session's todo list."""
    return _current_todos


def clear_todos() -> None:
    """Clear the current todo list."""
    global _current_todos
    _current_todos = None


def get_in_progress_todos() -> List[TodoItem]:
    """Get all in-progress todo items."""
    if _current_todos is None:
        return []
    return [item for item in _current_todos.items if item.status == TodoStatus.IN_PROGRESS]


def get_pending_todos() -> List[TodoItem]:
    """Get all pending todo items."""
    if _current_todos is None:
        return []
    return [item for item in _current_todos.items if item.status == TodoStatus.PENDING]


def format_todos_for_display(todo_list: Optional[TodoList] = None) -> str:
    """
    Format todos for user display.

    Args:
        todo_list: Optional todo list to format (uses current if not provided)

    Returns:
        Formatted string representation
    """
    todos = todo_list or _current_todos

    if todos is None or not todos.items:
        return "No tasks defined."

    lines = [f"📋 **{todos.task_name}**", ""]

    # Show in-progress first (prominently)
    in_progress = [item for item in todos.items if item.status == TodoStatus.IN_PROGRESS]
    if in_progress:
        lines.append("**Currently Working On:**")
        for item in in_progress:
            lines.append(f"  🔄 {item.description}")
        lines.append("")

    # Status icons
    status_icons = {
        TodoStatus.PENDING: "⬜",
        TodoStatus.IN_PROGRESS: "🔄",
        TodoStatus.COMPLETED: "✅",
        TodoStatus.CANCELLED: "❌",
    }

    lines.append("**All Tasks:**")
    for i, item in enumerate(todos.items, 1):
        icon = status_icons.get(item.status, "⬜")
        lines.append(f"  {i}. {icon} {item.description}")

    # Summary
    completed = sum(1 for item in todos.items if item.status == TodoStatus.COMPLETED)
    total = len(todos.items)
    lines.append("")
    lines.append(f"_Progress: {completed}/{total} completed_")

    return "\n".join(lines)


def _update_todos(
    todos: List[Dict[str, str]],
    task_name: str = "Current Task",
    session_id: str = "default",
) -> Dict[str, Any]:
    """
    Update the todo list with new items.

    Args:
        todos: List of todo dictionaries with description and status
        task_name: Name of the overall task
        session_id: Session identifier

    Returns:
        Dictionary with update status
    """
    global _current_todos

    try:
        items = []
        for todo_dict in todos:
            description = todo_dict.get("description", "").strip()
            if not description:
                continue

            status_str = todo_dict.get("status", "pending")
            try:
                status = TodoStatus(status_str)
            except ValueError:
                status = TodoStatus.PENDING

            item = TodoItem(
                description=description,
                status=status,
                updated_at=datetime.now().isoformat(),
            )
            items.append(item)

        if not items:
            return {
                "success": False,
                "error": "No valid todo items provided",
            }

        _current_todos = TodoList(
            session_id=session_id,
            task_name=task_name,
            items=items,
        )

        # Calculate statistics
        stats = {
            "pending": sum(1 for i in items if i.status == TodoStatus.PENDING),
            "in_progress": sum(1 for i in items if i.status == TodoStatus.IN_PROGRESS),
            "completed": sum(1 for i in items if i.status == TodoStatus.COMPLETED),
            "cancelled": sum(1 for i in items if i.status == TodoStatus.CANCELLED),
        }

        logger.info(f"Updated todos: {len(items)} items for task '{task_name}'")

        return {
            "success": True,
            "message": f"Updated task list with {len(items)} items",
            "task_name": task_name,
            "total_items": len(items),
            "statistics": stats,
            "display": format_todos_for_display(),
        }

    except Exception as e:
        error_msg = f"Failed to update todos: {str(e)}"
        logger.error(error_msg)
        return {
            "success": False,
            "error": error_msg,
        }


# Register the tool
@register_tool(
    name="write_todos",
    description="Track a multi-step task as a todo list shown to the user. Send the whole list each time; statuses: pending, in_progress (one at a time), completed, cancelled.",
    parameters={
        "type": "object",
        "properties": {
            "task_name": {
                "type": "string",
                "description": "Name or title of the overall task being broken down",
            },
            "todos": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "description": {
                            "type": "string",
                            "description": "Description of the subtask",
                        },
                        "status": {
                            "type": "string",
                            "enum": ["pending", "in_progress", "completed", "cancelled"],
                            "description": "Current status of the subtask",
                        },
                    },
                    "required": ["description"],
                },
                "description": "List of subtasks with descriptions and statuses",
            },
        },
        "required": ["todos"],
    },
    enabled=True,
    requires_approval=False,
)
def write_todos_tool(
    todos: List[Dict[str, str]],
    task_name: str = "Current Task",
) -> Dict[str, Any]:
    """
    Create or update a task list with subtasks.

    Args:
        todos: List of todo dictionaries
        task_name: Name of the overall task

    Returns:
        Dictionary with update status and display-ready content
    """
    if not todos:
        return {
            "success": False,
            "error": "No todos provided",
        }

    return _update_todos(todos, task_name)
