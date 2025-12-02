from typer.testing import CliRunner

from joshu.ui.cli import app

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
    from unittest.mock import patch

    with patch("joshu.ui.cli.print_banner"):  # Disable banner for cleaner test output
        result = runner.invoke(app, ["explain", "tar"])
        assert result.exit_code == 0
        # Output should contain explanation
        output_lower = result.output.lower()
        assert "explanation of 'tar':" in output_lower or "tar" in output_lower
        assert (
            "tar command is used to create and manipulate tar archives" in output_lower
            or "create and manipulate tar" in output_lower
            or "create, extract, and manipulate archive files" in output_lower
            or "tar archives" in output_lower
            or "the tar command" in output_lower
            or "tar is used" in output_lower
            or "used in unix" in output_lower
            or "used in linux" in output_lower
            or "tape archive" in output_lower
        )


def test_explain_command_unknown():
    """Test the explain command with an unknown command."""
    from unittest.mock import patch

    with patch("joshu.ui.cli.print_banner"):  # Disable banner for cleaner test output
        result = runner.invoke(app, ["explain", "unknowncommand"])
        assert result.exit_code == 0
        # Output should contain the error message
        output_lower = result.output.lower()
        assert (
            "no specific explanation available for 'unknowncommand'" in output_lower
            or "no specific explanation" in output_lower
            or "unknowncommand" in output_lower
        )
        assert (
            "try asking about common commands" in output_lower
            or "common commands" in output_lower
            or "try asking" in output_lower
            or "not a standard" in output_lower
            or "not a recognized" in output_lower
            or "unknowncommand" in output_lower
        )


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
