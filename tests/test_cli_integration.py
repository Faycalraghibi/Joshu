import pytest
from unittest.mock import patch, MagicMock
from joshu.ui.cli import app
import typer
from typer.testing import CliRunner

runner = CliRunner()

def test_cli_help():
    """Test that CLI help works."""
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "Joshu - Natural language meets your terminal." in result.stdout


def test_cli_version():
    """Test that CLI version works."""
    result = runner.invoke(app, ["--version"])
    # When --version is used, typer.Exit() is raised which sets exit_code to 0
    assert result.exit_code == 0
    assert "Joshu v" in result.stdout


@patch('joshu.ui.cli.translate_to_command')
@patch('joshu.ui.cli.assess_command_safety')
@patch('joshu.ui.cli.run_command')
def test_cli_run_success(mock_run_command, mock_assess_safety, mock_translate):
    """Test successful CLI run command."""
    # Mock the translation
    mock_translation = MagicMock()
    mock_translation.command = "echo hello"
    mock_translation.explanation = "Print hello"
    mock_translate.return_value = mock_translation
    
    # Mock the safety assessment
    mock_safety_report = MagicMock()
    mock_safety_report.safe = True
    mock_assess_safety.return_value = mock_safety_report
    
    # Mock the command execution
    mock_run_command.return_value = (0, "hello\n", "")
    
    # Run the CLI command
    result = runner.invoke(app, ["run", "say hello"], input="y\n")
    
    assert result.exit_code == 0
    assert "hello" in result.stdout


@patch('joshu.ui.cli.translate_to_command')
def test_cli_run_no_translation(mock_translate):
    """Test CLI run command with no translation."""
    mock_translate.return_value = None
    
    result = runner.invoke(app, ["run", "unknown command"])
    
    assert result.exit_code == 2
    assert "No translation found" in result.stdout