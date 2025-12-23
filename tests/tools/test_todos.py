"""
Tests for the Todos Tool (write_todos).
"""

from joshu.tools.todos import (
    TodoItem,
    TodoList,
    TodoStatus,
    clear_todos,
    format_todos_for_display,
    get_current_todos,
    get_in_progress_todos,
    get_pending_todos,
    write_todos_tool,
)


class TestTodoStatus:
    """Tests for TodoStatus enum."""

    def test_status_values(self):
        """All expected status values should exist."""
        assert TodoStatus.PENDING.value == "pending"
        assert TodoStatus.IN_PROGRESS.value == "in_progress"
        assert TodoStatus.COMPLETED.value == "completed"
        assert TodoStatus.CANCELLED.value == "cancelled"


class TestTodoItem:
    """Tests for TodoItem dataclass."""

    def test_create_todo_item(self):
        """Should create a todo item with default status."""
        item = TodoItem(description="Test task")

        assert item.description == "Test task"
        assert item.status == TodoStatus.PENDING
        assert item.created_at is not None

    def test_todo_item_to_dict(self):
        """Should convert to dictionary correctly."""
        item = TodoItem(description="Test task", status=TodoStatus.IN_PROGRESS)

        data = item.to_dict()

        assert data["description"] == "Test task"
        assert data["status"] == "in_progress"
        assert "created_at" in data

    def test_todo_item_from_dict(self):
        """Should create from dictionary."""
        data = {
            "description": "Test task",
            "status": "completed",
        }

        item = TodoItem.from_dict(data)

        assert item.description == "Test task"
        assert item.status == TodoStatus.COMPLETED


class TestTodoList:
    """Tests for TodoList dataclass."""

    def test_create_todo_list(self):
        """Should create a todo list."""
        items = [
            TodoItem(description="Task 1"),
            TodoItem(description="Task 2"),
        ]
        todo_list = TodoList(
            session_id="test-session",
            task_name="Test Task",
            items=items,
        )

        assert todo_list.session_id == "test-session"
        assert todo_list.task_name == "Test Task"
        assert len(todo_list.items) == 2

    def test_todo_list_to_dict(self):
        """Should convert to dictionary."""
        todo_list = TodoList(
            session_id="test",
            task_name="Test",
            items=[TodoItem(description="Task 1")],
        )

        data = todo_list.to_dict()

        assert data["session_id"] == "test"
        assert data["task_name"] == "Test"
        assert len(data["items"]) == 1


class TestWriteTodosTool:
    """Tests for the write_todos tool."""

    def setup_method(self):
        """Clear todos before each test."""
        clear_todos()

    def test_write_todos_success(self):
        """Should successfully write todos."""
        todos = [
            {"description": "Task 1", "status": "pending"},
            {"description": "Task 2", "status": "in_progress"},
        ]

        result = write_todos_tool(todos, task_name="Test Project")

        assert result["success"] is True
        assert result["total_items"] == 2
        assert result["task_name"] == "Test Project"

    def test_write_todos_empty_list(self):
        """Should fail with empty list."""
        result = write_todos_tool([])

        assert result["success"] is False
        assert "error" in result

    def test_write_todos_filters_empty_descriptions(self):
        """Should filter out items with empty descriptions."""
        todos = [
            {"description": "", "status": "pending"},
            {"description": "Valid task", "status": "pending"},
            {"description": "  ", "status": "pending"},
        ]

        result = write_todos_tool(todos)

        assert result["success"] is True
        assert result["total_items"] == 1

    def test_write_todos_default_status(self):
        """Should use pending as default status."""
        todos = [{"description": "Task without status"}]

        result = write_todos_tool(todos)

        assert result["success"] is True
        current = get_current_todos()
        assert current.items[0].status == TodoStatus.PENDING

    def test_write_todos_invalid_status(self):
        """Should default to pending for invalid status."""
        todos = [{"description": "Task", "status": "invalid_status"}]

        result = write_todos_tool(todos)

        assert result["success"] is True
        current = get_current_todos()
        assert current.items[0].status == TodoStatus.PENDING


class TestTodoHelpers:
    """Tests for todo helper functions."""

    def setup_method(self):
        """Set up todos for each test."""
        clear_todos()
        write_todos_tool(
            [
                {"description": "Pending 1", "status": "pending"},
                {"description": "In Progress 1", "status": "in_progress"},
                {"description": "Completed 1", "status": "completed"},
                {"description": "Pending 2", "status": "pending"},
            ]
        )

    def test_get_in_progress_todos(self):
        """Should return only in-progress items."""
        in_progress = get_in_progress_todos()

        assert len(in_progress) == 1
        assert in_progress[0].description == "In Progress 1"

    def test_get_pending_todos(self):
        """Should return only pending items."""
        pending = get_pending_todos()

        assert len(pending) == 2
        assert all(item.status == TodoStatus.PENDING for item in pending)

    def test_get_current_todos(self):
        """Should return the current todo list."""
        current = get_current_todos()

        assert current is not None
        assert len(current.items) == 4


class TestFormatTodosForDisplay:
    """Tests for formatting todos for display."""

    def setup_method(self):
        clear_todos()

    def test_format_empty_todos(self):
        """Should handle no todos gracefully."""
        display = format_todos_for_display()

        assert "No tasks defined" in display

    def test_format_with_todos(self):
        """Should format todos with status icons."""
        write_todos_tool(
            [
                {"description": "Task 1", "status": "pending"},
                {"description": "Task 2", "status": "in_progress"},
                {"description": "Task 3", "status": "completed"},
            ],
            task_name="My Project",
        )

        display = format_todos_for_display()

        assert "My Project" in display
        assert "Task 1" in display
        assert "Task 2" in display
        assert "Task 3" in display
        assert "Currently Working On" in display
        assert "Progress:" in display
