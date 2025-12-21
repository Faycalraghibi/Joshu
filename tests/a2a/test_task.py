"""
Tests for A2A Task and TaskState.
"""

import asyncio
from datetime import datetime

import pytest

from joshu.a2a.task import AbortController, AgentSettings, Task, TaskState


class TestTaskState:
    """Tests for TaskState enum."""

    def test_task_states_exist(self):
        """Test all required states exist."""
        assert TaskState.SUBMITTED.value == "submitted"
        assert TaskState.INPUT_REQUIRED.value == "input-required"
        assert TaskState.WORKING.value == "working"
        assert TaskState.CANCELED.value == "canceled"
        assert TaskState.FAILED.value == "failed"
        assert TaskState.COMPLETED.value == "completed"


class TestAbortController:
    """Tests for AbortController."""

    def test_initial_state(self):
        """Test controller is not aborted initially."""
        controller = AbortController()
        assert not controller.aborted
        assert controller.reason is None

    def test_abort(self):
        """Test aborting."""
        controller = AbortController()
        controller.abort("Test reason")
        assert controller.aborted
        assert controller.reason == "Test reason"

    def test_check_raises_when_aborted(self):
        """Test check raises CancelledError when aborted."""
        controller = AbortController()
        controller.abort("Canceled")
        with pytest.raises(asyncio.CancelledError):
            controller.check()

    def test_check_passes_when_not_aborted(self):
        """Test check passes when not aborted."""
        controller = AbortController()
        controller.check()  # Should not raise


class TestAgentSettings:
    """Tests for AgentSettings dataclass."""

    def test_default_settings(self):
        """Test default settings."""
        settings = AgentSettings()
        assert settings.model == "default"
        assert settings.target_directory == "."
        assert settings.tools_enabled is True
        assert settings.approval_mode == "safe_only"
        assert settings.system_prompt is None
        assert settings.extensions == []

    def test_custom_settings(self):
        """Test custom settings."""
        settings = AgentSettings(
            model="gpt-4",
            target_directory="/project",
            tools_enabled=False,
            approval_mode="manual",
            system_prompt="You are helpful",
            extensions=["ext1", "ext2"],
        )
        assert settings.model == "gpt-4"
        assert settings.target_directory == "/project"
        assert settings.tools_enabled is False
        assert settings.extensions == ["ext1", "ext2"]

    def test_to_dict(self):
        """Test serialization."""
        settings = AgentSettings(model="test")
        data = settings.to_dict()
        assert data["model"] == "test"
        assert "target_directory" in data
        assert "tools_enabled" in data

    def test_from_dict(self):
        """Test deserialization."""
        data = {
            "model": "claude",
            "target_directory": "/home",
            "tools_enabled": True,
            "approval_mode": "auto",
        }
        settings = AgentSettings.from_dict(data)
        assert settings.model == "claude"
        assert settings.target_directory == "/home"

    def test_from_dict_with_defaults(self):
        """Test deserialization with missing fields uses defaults."""
        data = {"model": "test"}
        settings = AgentSettings.from_dict(data)
        assert settings.model == "test"
        assert settings.target_directory == "."  # Default


class TestTask:
    """Tests for Task class."""

    def test_create_task(self):
        """Test creating a new task."""
        settings = AgentSettings(model="test")
        task = Task.create(settings)

        assert task.task_id is not None
        assert task.state == TaskState.SUBMITTED
        assert task.settings.model == "test"
        assert task.session is not None
        assert task.scheduler is not None
        assert task.abort_controller is not None
        assert isinstance(task.created_at, datetime)

    def test_create_task_with_id(self):
        """Test creating task with specific ID."""
        task = Task.create(AgentSettings(), task_id="my-task-123")
        assert task.task_id == "my-task-123"

    def test_state_transitions(self):
        """Test state transitions."""
        task = Task.create(AgentSettings())
        assert task.state == TaskState.SUBMITTED

        task.start()
        assert task.state == TaskState.WORKING

        task.request_input("call-1")
        assert task.state == TaskState.INPUT_REQUIRED
        assert task.pending_confirmation == "call-1"

        task.resume()
        assert task.state == TaskState.WORKING
        assert task.pending_confirmation is None

        task.complete()
        assert task.state == TaskState.COMPLETED

    def test_fail_state(self):
        """Test failing a task."""
        task = Task.create(AgentSettings())
        task.start()
        task.fail("Something went wrong")

        assert task.state == TaskState.FAILED
        assert task.metadata["error"] == "Something went wrong"

    def test_cancel_state(self):
        """Test canceling a task."""
        task = Task.create(AgentSettings())
        task.start()
        task.cancel("User requested")

        assert task.state == TaskState.CANCELED
        assert task.metadata["cancel_reason"] == "User requested"
        assert task.abort_controller.aborted

    def test_is_terminal(self):
        """Test is_terminal property."""
        task = Task.create(AgentSettings())
        assert not task.is_terminal

        task.start()
        assert not task.is_terminal

        task.complete()
        assert task.is_terminal

    def test_is_active(self):
        """Test is_active property."""
        task = Task.create(AgentSettings())
        assert not task.is_active

        task.start()
        assert task.is_active

        task.complete()
        assert not task.is_active

    def test_to_dict(self):
        """Test serialization."""
        settings = AgentSettings(model="test-model")
        task = Task.create(settings, task_id="test-123")
        task.start()

        data = task.to_dict()

        assert data["task_id"] == "test-123"
        assert data["state"] == "working"
        assert data["settings"]["model"] == "test-model"
        assert "session_state" in data
        assert "scheduler_state" in data
        assert "created_at" in data
        assert "updated_at" in data

    def test_from_dict(self):
        """Test deserialization."""
        # Create and serialize a task
        original = Task.create(AgentSettings(model="original"))
        original.start()
        data = original.to_dict()

        # Reconstruct from serialized data
        restored = Task.from_dict(data)

        assert restored.task_id == original.task_id
        assert restored.state == TaskState.WORKING
        assert restored.settings.model == "original"
        assert restored.abort_controller is not None

    def test_updated_at_changes(self):
        """Test that updated_at changes on state transition."""
        task = Task.create(AgentSettings())
        initial_updated = task.updated_at

        # Small delay to ensure time difference
        import time

        time.sleep(0.01)

        task.start()
        assert task.updated_at > initial_updated
