from typer.testing import CliRunner

from joshu.ui.cli import app

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
