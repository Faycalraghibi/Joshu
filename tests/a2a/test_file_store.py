"""
Tests for FileTaskStore.
"""

import tempfile
from pathlib import Path

import pytest

from joshu.a2a.task import AgentSettings, Task
from joshu.a2a.task_store import FileTaskStore, validate_task_id


class TestValidateTaskId:
    """Tests for task ID validation."""

    def test_valid_task_ids(self):
        """Test valid task IDs."""
        assert validate_task_id("abc123") is True
        assert validate_task_id("task-1") is True
        assert validate_task_id("task_2") is True
        assert validate_task_id("ABC-123_xyz") is True

    def test_invalid_task_ids(self):
        """Test invalid task IDs (path traversal attempts)."""
        assert validate_task_id("") is False
        assert validate_task_id("..") is False
        assert validate_task_id("../etc/passwd") is False
        assert validate_task_id("/etc/passwd") is False
        assert validate_task_id("foo/bar") is False
        assert validate_task_id("foo\\bar") is False
        assert validate_task_id("task..id") is False


class TestFileTaskStore:
    """Tests for FileTaskStore."""

    @pytest.fixture
    def temp_storage(self):
        """Create temporary storage directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def store(self, temp_storage):
        """Create FileTaskStore with temp directory."""
        return FileTaskStore(temp_storage)

    def test_save_and_get(self, store):
        """Test saving and retrieving a task."""
        task = Task.create(AgentSettings(), task_id="test-123")

        result = store.save(task)
        assert result is True

        retrieved = store.get("test-123")
        assert retrieved is not None
        assert retrieved.task_id == "test-123"

    def test_get_nonexistent(self, store):
        """Test getting nonexistent task."""
        assert store.get("nonexistent") is None

    def test_save_creates_gzip(self, store, temp_storage):
        """Test that save creates gzipped file."""
        task = Task.create(AgentSettings(), task_id="test-123")
        store.save(task)

        metadata_path = temp_storage / "test-123" / "metadata.json.gz"
        assert metadata_path.exists()

    def test_delete(self, store):
        """Test deleting a task."""
        task = Task.create(AgentSettings(), task_id="test-123")
        store.save(task)

        result = store.delete("test-123")
        assert result is True
        assert store.get("test-123") is None

    def test_delete_nonexistent(self, store):
        """Test deleting nonexistent task."""
        assert store.delete("nonexistent") is False

    def test_list_tasks(self, store):
        """Test listing task IDs."""
        for i in range(3):
            task = Task.create(AgentSettings(), task_id=f"task-{i}")
            store.save(task)

        ids = store.list_tasks()
        assert len(ids) == 3
        assert all(f"task-{i}" in ids for i in range(3))

    def test_list_tasks_with_limit(self, store):
        """Test listing with limit."""
        for i in range(10):
            task = Task.create(AgentSettings(), task_id=f"task-{i}")
            store.save(task)

        ids = store.list_tasks(limit=5)
        assert len(ids) == 5

    def test_path_traversal_save_rejected(self, store):
        """Test that path traversal is rejected on save."""
        task = Task.create(AgentSettings())
        task.task_id = "../malicious"  # Attempt path traversal

        result = store.save(task)
        assert result is False

    def test_path_traversal_get_rejected(self, store):
        """Test that path traversal is rejected on get."""
        result = store.get("../etc/passwd")
        assert result is None

    def test_path_traversal_delete_rejected(self, store):
        """Test that path traversal is rejected on delete."""
        result = store.delete("../../..")
        assert result is False

    def test_save_workspace(self, store, temp_storage):
        """Test saving workspace."""
        task = Task.create(AgentSettings(), task_id="test-123")
        store.save(task)

        # Create a test workspace
        workspace = temp_storage / "workspace"
        workspace.mkdir()
        (workspace / "file.txt").write_text("hello")

        result = store.save_workspace("test-123", workspace)
        assert result is True

        # Verify tarball exists
        tarball = temp_storage / "test-123" / "workspace.tar.gz"
        assert tarball.exists()

    def test_restore_workspace(self, store, temp_storage):
        """Test restoring workspace."""
        task = Task.create(AgentSettings(), task_id="test-123")
        store.save(task)

        # Create and save workspace
        workspace = temp_storage / "workspace"
        workspace.mkdir()
        (workspace / "file.txt").write_text("hello world")
        store.save_workspace("test-123", workspace)

        # Restore to new location
        restore_dir = temp_storage / "restored"
        result = store.restore_workspace("test-123", restore_dir)
        assert result is True

        # Verify content
        restored_file = restore_dir / "workspace" / "file.txt"
        assert restored_file.exists()
        assert restored_file.read_text() == "hello world"

    def test_get_storage_size(self, store):
        """Test getting storage size."""
        task = Task.create(AgentSettings(), task_id="test-123")
        store.save(task)

        size = store.get_storage_size("test-123")
        assert size is not None
        assert size > 0

    def test_get_storage_size_nonexistent(self, store):
        """Test getting storage size for nonexistent task."""
        size = store.get_storage_size("nonexistent")
        assert size is None

    def test_exists(self, store):
        """Test exists check."""
        task = Task.create(AgentSettings(), task_id="test-123")

        assert store.exists("test-123") is False
        store.save(task)
        assert store.exists("test-123") is True
