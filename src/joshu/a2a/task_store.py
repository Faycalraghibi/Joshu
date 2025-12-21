"""
A2A Task persistence and storage.

This module provides TaskStore abstraction and implementations
for persisting task state, enabling task reconstruction.

NOTE: This module provides transport and orchestration only.
It must not introduce new agent logic or execution semantics.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Dict, List, Optional

from joshu.a2a.task import Task

logger = logging.getLogger(__name__)


class TaskStore(ABC):
    """
    Abstract base class for task persistence.

    Provides methods for saving, retrieving, and deleting tasks.
    Implementations may use in-memory storage, file storage,
    or cloud storage (e.g., GCS).
    """

    @abstractmethod
    def save(self, task: Task) -> bool:
        """
        Save a task to storage.

        Args:
            task: The task to save

        Returns:
            True if successful, False otherwise
        """
        pass

    @abstractmethod
    def get(self, task_id: str) -> Optional[Task]:
        """
        Get a task by ID.

        Args:
            task_id: The task ID to retrieve

        Returns:
            The task if found, None otherwise
        """
        pass

    @abstractmethod
    def delete(self, task_id: str) -> bool:
        """
        Delete a task by ID.

        Args:
            task_id: The task ID to delete

        Returns:
            True if deleted, False if not found
        """
        pass

    @abstractmethod
    def list_tasks(self, limit: int = 100) -> List[str]:
        """
        List task IDs in storage.

        Args:
            limit: Maximum number of IDs to return

        Returns:
            List of task IDs
        """
        pass

    def exists(self, task_id: str) -> bool:
        """
        Check if a task exists.

        Args:
            task_id: The task ID to check

        Returns:
            True if exists, False otherwise
        """
        return self.get(task_id) is not None


class InMemoryTaskStore(TaskStore):
    """
    In-memory task storage for development and testing.

    Tasks are stored in a dictionary and are lost when
    the process exits.
    """

    def __init__(self) -> None:
        self._tasks: Dict[str, Dict] = {}
        logger.debug("Initialized InMemoryTaskStore")

    def save(self, task: Task) -> bool:
        """Save task to memory."""
        try:
            self._tasks[task.task_id] = task.to_dict()
            logger.debug(f"Saved task {task.task_id} to memory")
            return True
        except Exception as e:
            logger.error(f"Failed to save task {task.task_id}: {e}")
            return False

    def get(self, task_id: str) -> Optional[Task]:
        """Get task from memory."""
        data = self._tasks.get(task_id)
        if data is None:
            return None
        try:
            return Task.from_dict(data)
        except Exception as e:
            logger.error(f"Failed to reconstruct task {task_id}: {e}")
            return None

    def delete(self, task_id: str) -> bool:
        """Delete task from memory."""
        if task_id in self._tasks:
            del self._tasks[task_id]
            logger.debug(f"Deleted task {task_id} from memory")
            return True
        return False

    def list_tasks(self, limit: int = 100) -> List[str]:
        """List task IDs in memory."""
        return list(self._tasks.keys())[:limit]

    def clear(self) -> None:
        """Clear all tasks (for testing)."""
        self._tasks.clear()
        logger.debug("Cleared all tasks from memory")


class NoOpTaskStore(TaskStore):
    """
    No-operation task store.

    Does not persist anything. Useful when persistence
    is not needed or is handled externally.
    """

    def save(self, task: Task) -> bool:
        """No-op save - always returns True."""
        logger.debug(f"NoOp: Would save task {task.task_id}")
        return True

    def get(self, task_id: str) -> Optional[Task]:
        """No-op get - always returns None."""
        logger.debug(f"NoOp: Would get task {task_id}")
        return None

    def delete(self, task_id: str) -> bool:
        """No-op delete - always returns True."""
        logger.debug(f"NoOp: Would delete task {task_id}")
        return True

    def list_tasks(self, limit: int = 100) -> List[str]:
        """No-op list - always returns empty list."""
        return []

    def exists(self, task_id: str) -> bool:
        """No-op exists - always returns False."""
        return False


# Module-level store instance
_store: Optional[TaskStore] = None


def get_task_store() -> TaskStore:
    """
    Get the global task store instance.

    Returns:
        TaskStore singleton instance (InMemoryTaskStore by default)
    """
    global _store
    if _store is None:
        _store = InMemoryTaskStore()
    return _store


def set_task_store(store: TaskStore) -> None:
    """
    Set the global task store instance.

    Args:
        store: The TaskStore implementation to use
    """
    global _store
    _store = store
    logger.info(f"Task store set to {type(store).__name__}")
