"""
Tests for A2A CommandRegistry and Command types.
"""

from pathlib import Path

import pytest

from joshu.a2a.commands.registry import CommandRegistry
from joshu.a2a.commands.types import (
    BaseCommand,
    CommandArgument,
    CommandContext,
    CommandResult,
    CommandStatus,
)


class TestCommandArgument:
    """Tests for CommandArgument."""

    def test_create_argument(self):
        """Test creating a command argument."""
        arg = CommandArgument(
            name="file",
            description="File to process",
            arg_type="string",
            required=True,
        )
        assert arg.name == "file"
        assert arg.description == "File to process"
        assert arg.arg_type == "string"
        assert arg.required is True

    def test_to_dict(self):
        """Test serialization."""
        arg = CommandArgument(
            name="count",
            description="Number of items",
            arg_type="int",
            default=10,
        )
        data = arg.to_dict()
        assert data["name"] == "count"
        assert data["type"] == "int"
        assert data["default"] == 10


class TestCommandResult:
    """Tests for CommandResult."""

    def test_success_result(self):
        """Test creating success result."""
        result = CommandResult.success("Operation completed", {"items": 5})
        assert result.status == CommandStatus.SUCCESS
        assert result.message == "Operation completed"
        assert result.data == {"items": 5}

    def test_error_result(self):
        """Test creating error result via constructor."""
        result = CommandResult(
            status=CommandStatus.ERROR,
            message="Connection timeout",
            error_message="Failed to connect",
        )
        assert result.status == CommandStatus.ERROR
        assert result.error_message == "Failed to connect"
        assert result.message == "Connection timeout"

    def test_make_error_factory(self):
        """Test make_error factory method."""
        result = CommandResult.make_error("Some error", "Error occurred")
        assert result.status == CommandStatus.ERROR
        assert result.error_message == "Some error"
        assert result.message == "Error occurred"

    def test_to_dict(self):
        """Test serialization."""
        result = CommandResult.success("Done")
        data = result.to_dict()
        assert data["status"] == "success"
        assert data["message"] == "Done"


class TestCommandContext:
    """Tests for CommandContext."""

    def test_create_context(self):
        """Test creating command context."""
        ctx = CommandContext(
            workspace_path=Path("/tmp/workspace"),
            config={"key": "value"},
        )
        assert ctx.workspace_path == Path("/tmp/workspace")
        assert ctx.config == {"key": "value"}

    def test_get_config(self):
        """Test getting config values."""
        ctx = CommandContext(
            workspace_path=Path("."),
            config={"debug": True, "timeout": 30},
        )
        assert ctx.get_config("debug") is True
        assert ctx.get_config("timeout") == 30
        assert ctx.get_config("missing", "default") == "default"


class TestBaseCommand:
    """Tests for BaseCommand."""

    def test_create_command(self):
        """Test creating a base command."""
        cmd = BaseCommand(
            _name="test",
            _description="Test command",
            _arguments=[CommandArgument("arg1", "First arg")],
        )
        assert cmd.name == "test"
        assert cmd.description == "Test command"
        assert len(cmd.arguments) == 1
        assert len(cmd.subcommands) == 0

    def test_add_subcommand(self):
        """Test adding subcommand."""
        parent = BaseCommand(_name="parent", _description="Parent")
        child = BaseCommand(_name="child", _description="Child")
        parent.add_subcommand(child)
        assert len(parent.subcommands) == 1
        assert parent.subcommands[0].name == "child"

    def test_to_dict(self):
        """Test serialization."""
        cmd = BaseCommand(
            _name="cmd",
            _description="Description",
            _arguments=[CommandArgument("arg", "Arg desc")],
        )
        data = cmd.to_dict()
        assert data["name"] == "cmd"
        assert data["description"] == "Description"
        assert len(data["arguments"]) == 1


class TestCommandRegistry:
    """Tests for CommandRegistry."""

    def test_register_command(self):
        """Test registering a command."""
        registry = CommandRegistry()
        cmd = BaseCommand(_name="test", _description="Test")
        registry.register(cmd)
        assert registry.has("test")

    def test_register_duplicate_raises(self):
        """Test registering duplicate raises ValueError."""
        registry = CommandRegistry()
        cmd = BaseCommand(_name="test", _description="Test")
        registry.register(cmd)
        with pytest.raises(ValueError):
            registry.register(cmd)

    def test_get_command(self):
        """Test getting a command."""
        registry = CommandRegistry()
        cmd = BaseCommand(_name="test", _description="Test")
        registry.register(cmd)
        retrieved = registry.get("test")
        assert retrieved is not None
        assert retrieved.name == "test"

    def test_get_nonexistent(self):
        """Test getting nonexistent command."""
        registry = CommandRegistry()
        assert registry.get("nonexistent") is None

    def test_get_subcommand(self):
        """Test getting subcommand with dotted notation."""
        registry = CommandRegistry()
        parent = BaseCommand(_name="parent", _description="Parent")
        child = BaseCommand(_name="child", _description="Child")
        parent.add_subcommand(child)
        registry.register(parent)

        # Get subcommand via dotted notation
        sub = registry.get("parent.child")
        assert sub is not None
        assert sub.name == "child"

    def test_unregister(self):
        """Test unregistering a command."""
        registry = CommandRegistry()
        cmd = BaseCommand(_name="test", _description="Test")
        registry.register(cmd)
        assert registry.unregister("test") is True
        assert registry.has("test") is False

    def test_get_all(self):
        """Test getting all commands."""
        registry = CommandRegistry()
        registry.register(BaseCommand(_name="cmd1", _description="One"))
        registry.register(BaseCommand(_name="cmd2", _description="Two"))
        all_cmds = registry.get_all()
        assert len(all_cmds) == 2

    def test_list_commands(self):
        """Test listing commands for API."""
        registry = CommandRegistry()
        parent = BaseCommand(
            _name="test",
            _description="Test command",
            _arguments=[CommandArgument("arg", "Argument")],
        )
        child = BaseCommand(_name="sub", _description="Subcommand")
        parent.add_subcommand(child)
        registry.register(parent)

        listing = registry.list_commands()
        assert len(listing) == 1
        assert listing[0]["name"] == "test"
        assert len(listing[0]["arguments"]) == 1
        assert len(listing[0]["subcommands"]) == 1
        assert listing[0]["subcommands"][0]["name"] == "sub"

    def test_clear(self):
        """Test clearing registry."""
        registry = CommandRegistry()
        registry.register(BaseCommand(_name="test", _description="Test"))
        registry.clear()
        assert len(registry.get_all()) == 0
