"""
Tests for A2A TaskStore implementations.
"""

from joshu.a2a.task import AgentSettings, Task, TaskState
from joshu.a2a.task_store import (
    InMemoryTaskStore,
    NoOpTaskStore,
    get_task_store,
    set_task_store,
)


class TestInMemoryTaskStore:
    """Tests for InMemoryTaskStore."""

    def test_save_and_get(self):
        """Test saving and retrieving a task."""
        store = InMemoryTaskStore()
        task = Task.create(AgentSettings(), task_id="test-123")

        result = store.save(task)
        assert result is True

        retrieved = store.get("test-123")
        assert retrieved is not None
        assert retrieved.task_id == "test-123"

    def test_get_nonexistent(self):
        """Test getting a task that doesn't exist."""
        store = InMemoryTaskStore()
        result = store.get("nonexistent")
        assert result is None

    def test_delete(self):
        """Test deleting a task."""
        store = InMemoryTaskStore()
        task = Task.create(AgentSettings(), task_id="test-123")
        store.save(task)

        result = store.delete("test-123")
        assert result is True

        # Should no longer exist
        assert store.get("test-123") is None

    def test_delete_nonexistent(self):
        """Test deleting a task that doesn't exist."""
        store = InMemoryTaskStore()
        result = store.delete("nonexistent")
        assert result is False

    def test_list_tasks(self):
        """Test listing task IDs."""
        store = InMemoryTaskStore()
        task1 = Task.create(AgentSettings(), task_id="task-1")
        task2 = Task.create(AgentSettings(), task_id="task-2")
        task3 = Task.create(AgentSettings(), task_id="task-3")

        store.save(task1)
        store.save(task2)
        store.save(task3)

        ids = store.list_tasks()
        assert len(ids) == 3
        assert "task-1" in ids
        assert "task-2" in ids
        assert "task-3" in ids

    def test_list_tasks_with_limit(self):
        """Test listing with limit."""
        store = InMemoryTaskStore()
        for i in range(10):
            task = Task.create(AgentSettings(), task_id=f"task-{i}")
            store.save(task)

        ids = store.list_tasks(limit=5)
        assert len(ids) == 5

    def test_exists(self):
        """Test exists check."""
        store = InMemoryTaskStore()
        task = Task.create(AgentSettings(), task_id="test-123")

        assert store.exists("test-123") is False
        store.save(task)
        assert store.exists("test-123") is True

    def test_clear(self):
        """Test clearing all tasks."""
        store = InMemoryTaskStore()
        for i in range(3):
            task = Task.create(AgentSettings(), task_id=f"task-{i}")
            store.save(task)

        assert len(store.list_tasks()) == 3
        store.clear()
        assert len(store.list_tasks()) == 0

    def test_update_existing_task(self):
        """Test updating an existing task."""
        store = InMemoryTaskStore()
        task = Task.create(AgentSettings(), task_id="test-123")
        store.save(task)

        # Get and modify
        retrieved = store.get("test-123")
        retrieved.start()
        store.save(retrieved)

        # Verify update persisted
        updated = store.get("test-123")
        assert updated.state == TaskState.WORKING


class TestNoOpTaskStore:
    """Tests for NoOpTaskStore."""

    def test_save_returns_true(self):
        """Test save always returns True."""
        store = NoOpTaskStore()
        task = Task.create(AgentSettings())
        assert store.save(task) is True

    def test_get_returns_none(self):
        """Test get always returns None."""
        store = NoOpTaskStore()
        task = Task.create(AgentSettings(), task_id="test-123")
        store.save(task)
        assert store.get("test-123") is None

    def test_delete_returns_true(self):
        """Test delete always returns True."""
        store = NoOpTaskStore()
        assert store.delete("any-id") is True

    def test_list_returns_empty(self):
        """Test list always returns empty."""
        store = NoOpTaskStore()
        task = Task.create(AgentSettings())
        store.save(task)
        assert store.list_tasks() == []

    def test_exists_returns_false(self):
        """Test exists always returns False."""
        store = NoOpTaskStore()
        assert store.exists("any-id") is False


class TestGlobalTaskStore:
    """Tests for global task store functions."""

    def test_get_task_store_returns_singleton(self):
        """Test that get_task_store returns a singleton."""
        store1 = get_task_store()
        store2 = get_task_store()
        assert store1 is store2

    def test_set_task_store(self):
        """Test setting a custom task store."""
        custom = NoOpTaskStore()
        set_task_store(custom)

        retrieved = get_task_store()
        assert retrieved is custom

        # Reset to default for other tests
        set_task_store(InMemoryTaskStore())
