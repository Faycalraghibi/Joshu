"""
A2A Task persistence and storage.

This module provides TaskStore abstraction and implementations
for persisting task state, enabling task reconstruction.

NOTE: This module provides transport and orchestration only.
It must not introduce new agent logic or execution semantics.
"""

from __future__ import annotations

import gzip
import json
import logging
import re
import shutil
import tarfile
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, List, Optional

from joshu.a2a.task import Task

logger = logging.getLogger(__name__)


# Regex for validating task IDs (prevent path traversal)
TASK_ID_PATTERN = re.compile(r"^[a-zA-Z0-9_-]+$")


def validate_task_id(task_id: str) -> bool:
    """
    Validate task ID to prevent path traversal attacks.

    Args:
        task_id: The task ID to validate

    Returns:
        True if valid, False otherwise
    """
    if not task_id:
        return False
    if ".." in task_id or "/" in task_id or "\\" in task_id:
        return False
    return bool(TASK_ID_PATTERN.match(task_id))


class TaskStore(ABC):
    """
    Abstract base class for task persistence.

    Provides methods for saving, retrieving, and deleting tasks.
    Implementations may use in-memory storage, file storage,
    or cloud storage.
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


class FileTaskStore(TaskStore):
    """
    File-based task persistence with compression.

    Stores task metadata as gzipped JSON and workspaces
    as gzipped tarballs for efficient storage.

    Directory structure:
        {storage_dir}/
            {task_id}/
                metadata.json.gz
                workspace.tar.gz (optional)

    Attributes:
        storage_dir: Directory for storing task data
    """

    METADATA_FILENAME = "metadata.json.gz"
    WORKSPACE_FILENAME = "workspace.tar.gz"

    def __init__(self, storage_dir: Path) -> None:
        """
        Initialize FileTaskStore.

        Args:
            storage_dir: Directory for storing task data
        """
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        logger.debug(f"Initialized FileTaskStore at {self.storage_dir}")

    def _task_dir(self, task_id: str) -> Path:
        """Get directory for a specific task."""
        return self.storage_dir / task_id

    def _validate_and_get_task_dir(self, task_id: str) -> Optional[Path]:
        """Validate task ID and return task directory."""
        if not validate_task_id(task_id):
            logger.error(f"Invalid task ID: {task_id}")
            return None
        return self._task_dir(task_id)

    def save(self, task: Task) -> bool:
        """
        Save task with gzipped metadata.

        Args:
            task: Task to save

        Returns:
            True if successful, False otherwise
        """
        task_dir = self._validate_and_get_task_dir(task.task_id)
        if task_dir is None:
            return False

        try:
            # Create task directory
            task_dir.mkdir(parents=True, exist_ok=True)

            # Save metadata as gzipped JSON
            metadata_path = task_dir / self.METADATA_FILENAME
            metadata = task.to_dict()
            metadata_json = json.dumps(metadata, indent=2)

            with gzip.open(metadata_path, "wt", encoding="utf-8") as f:
                f.write(metadata_json)

            logger.debug(f"Saved task {task.task_id} to {task_dir}")
            return True

        except Exception as e:
            logger.error(f"Failed to save task {task.task_id}: {e}")
            return False

    def save_workspace(self, task_id: str, workspace_dir: Path) -> bool:
        """
        Save workspace directory as gzipped tarball.

        Args:
            task_id: Task ID
            workspace_dir: Directory to archive

        Returns:
            True if successful, False otherwise
        """
        task_dir = self._validate_and_get_task_dir(task_id)
        if task_dir is None:
            return False

        if not workspace_dir.exists():
            logger.error(f"Workspace directory not found: {workspace_dir}")
            return False

        try:
            workspace_path = task_dir / self.WORKSPACE_FILENAME

            with tarfile.open(workspace_path, "w:gz") as tar:
                tar.add(workspace_dir, arcname="workspace")

            logger.debug(f"Saved workspace for task {task_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to save workspace for task {task_id}: {e}")
            return False

    def get(self, task_id: str) -> Optional[Task]:
        """
        Get task from gzipped metadata.

        Args:
            task_id: Task ID to retrieve

        Returns:
            Task if found, None otherwise
        """
        task_dir = self._validate_and_get_task_dir(task_id)
        if task_dir is None:
            return None

        metadata_path = task_dir / self.METADATA_FILENAME
        if not metadata_path.exists():
            return None

        try:
            with gzip.open(metadata_path, "rt", encoding="utf-8") as f:
                metadata = json.load(f)

            return Task.from_dict(metadata)

        except Exception as e:
            logger.error(f"Failed to load task {task_id}: {e}")
            return None

    def restore_workspace(self, task_id: str, target_dir: Path) -> bool:
        """
        Restore workspace from gzipped tarball.

        Args:
            task_id: Task ID
            target_dir: Directory to extract to

        Returns:
            True if successful, False otherwise
        """
        task_dir = self._validate_and_get_task_dir(task_id)
        if task_dir is None:
            return False

        workspace_path = task_dir / self.WORKSPACE_FILENAME
        if not workspace_path.exists():
            logger.warning(f"No workspace archive for task {task_id}")
            return False

        try:
            target_dir.mkdir(parents=True, exist_ok=True)

            with tarfile.open(workspace_path, "r:gz") as tar:
                # Security: filter to prevent path traversal in tarball
                def safe_members(tar_file: tarfile.TarFile):
                    for member in tar_file.getmembers():
                        # Prevent absolute paths and path traversal
                        if member.name.startswith("/") or ".." in member.name:
                            logger.warning(f"Skipping unsafe path: {member.name}")
                            continue
                        yield member

                tar.extractall(target_dir, members=safe_members(tar))

            logger.debug(f"Restored workspace for task {task_id} to {target_dir}")
            return True

        except Exception as e:
            logger.error(f"Failed to restore workspace for task {task_id}: {e}")
            return False

    def delete(self, task_id: str) -> bool:
        """
        Delete task and its workspace.

        Args:
            task_id: Task ID to delete

        Returns:
            True if deleted, False if not found
        """
        task_dir = self._validate_and_get_task_dir(task_id)
        if task_dir is None:
            return False

        if not task_dir.exists():
            return False

        try:
            shutil.rmtree(task_dir)
            logger.debug(f"Deleted task {task_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to delete task {task_id}: {e}")
            return False

    def list_tasks(self, limit: int = 100) -> List[str]:
        """List task IDs in storage."""
        task_ids = []
        for item in self.storage_dir.iterdir():
            if item.is_dir() and validate_task_id(item.name):
                if (item / self.METADATA_FILENAME).exists():
                    task_ids.append(item.name)
                    if len(task_ids) >= limit:
                        break
        return task_ids

    def get_storage_size(self, task_id: str) -> Optional[int]:
        """
        Get total storage size for a task in bytes.

        Args:
            task_id: Task ID

        Returns:
            Size in bytes or None if task not found
        """
        task_dir = self._validate_and_get_task_dir(task_id)
        if task_dir is None or not task_dir.exists():
            return None

        total_size = 0
        for item in task_dir.iterdir():
            if item.is_file():
                total_size += item.stat().st_size

        return total_size


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
