import pytest
from typer.testing import CliRunner
from src.joshu.ui.cli import app

runner = CliRunner()


def test_examples_command():
    """Test the examples command."""
    result = runner.invoke(app, ["examples"])
    assert result.exit_code == 0
    assert "Joshu Usage Examples" in result.output
    assert "Basic Commands:" in result.output
    assert "File System Intelligence:" in result.output
    assert "Code Generation:" in result.output


def test_commands_command():
    """Test the commands command without category."""
    result = runner.invoke(app, ["commands"])
    assert result.exit_code == 0
    assert "Joshu Command Categories" in result.output
    assert "Available Categories:" in result.output
    assert "file" in result.output
    assert "system" in result.output


def test_commands_command_with_category():
    """Test the commands command with a specific category."""
    result = runner.invoke(app, ["commands", "file"])
    assert result.exit_code == 0
    assert "File System Commands:" in result.output
    assert "List files:" in result.output
    assert "Find files:" in result.output


def test_commands_command_with_unknown_category():
    """Test the commands command with an unknown category."""
    result = runner.invoke(app, ["commands", "unknown"])
    assert result.exit_code == 0
    assert "Unknown category: unknown" in result.output
    assert "Available Categories:" in result.output


def test_explain_command():
    """Test the explain command with a known command."""
    result = runner.invoke(app, ["explain", "tar"])
    assert result.exit_code == 0
    assert "Explanation of 'tar':" in result.output
    assert "tar command is used to create and manipulate tar archives" in result.output


def test_explain_command_unknown():
    """Test the explain command with an unknown command."""
    result = runner.invoke(app, ["explain", "unknowncommand"])
    assert result.exit_code == 0
    assert "No specific explanation available for 'unknowncommand'" in result.output
    assert "Try asking about common commands" in result.output


def test_help_command():
    """Test the built-in help command."""
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "Joshu - Natural language meets your terminal." in result.output
    # Check that our new commands are listed
    assert "commands" in result.output
    assert "examples" in result.output
    assert "explain" in result.output
    # Check for the Commands section header (in a box)
    assert "Commands" in result.output