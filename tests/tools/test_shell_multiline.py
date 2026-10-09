"""Multi-line commands on Windows without Git Bash: refused with advice instead of
silently not running (with Git Bash they run, see test_multiline_commands)."""

from unittest.mock import patch

from joshu.tools import shell_tool
from joshu.tools.shell_tool import multiline_error, run_shell_command_tool


def test_refused_on_windows():
    with (
        patch.object(shell_tool.os, "name", "nt"),
        patch.object(shell_tool, "git_bash", return_value=None),
    ):
        assert "write_file" in multiline_error('python -c "\nprint(1)\n"')
        assert multiline_error("cat <<EOF\nx\nEOF") is not None
        # One line, with or without a trailing newline, is fine
        assert multiline_error("python check.py\n") is None
        assert multiline_error("dir && echo ok") is None


def test_allowed_elsewhere():
    with patch.object(shell_tool.os, "name", "posix"):
        assert multiline_error("cat <<EOF\nx\nEOF") is None


def test_the_tool_does_not_run_it():
    with (
        patch.object(shell_tool.os, "name", "nt"),
        patch.object(shell_tool, "git_bash", return_value=None),
        patch.object(shell_tool, "run_shell_command") as run,
        patch.object(shell_tool, "start_background_process") as start,
    ):
        result = run_shell_command_tool('python -c "\nprint(1)\n"')
        background = run_shell_command_tool("a\nb", background=True)
    assert result["success"] is False and "cmd.exe" in result["error"]
    assert background["success"] is False
    run.assert_not_called()
    start.assert_not_called()
