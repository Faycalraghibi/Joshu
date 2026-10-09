"""Multi-line commands (python -c with several lines, heredocs) run on every platform
that can: on Windows through Git Bash, since cmd.exe runs only the first line."""

import os
import sys

import pytest

from joshu.tools import shell_tool

windows_without_bash = os.name == "nt" and shell_tool.git_bash() is None


@pytest.mark.skipif(windows_without_bash, reason="needs Git Bash on Windows")
def test_multi_line_python_runs(tmp_path):
    python = sys.executable.replace("\\", "/")
    result = shell_tool.run_shell_command_tool(
        f'"{python}" -c "print(1)\nprint(2)"', working_directory=str(tmp_path)
    )
    assert result["exit_code"] == 0 and result["stdout"].split() == ["1", "2"]


@pytest.mark.skipif(windows_without_bash, reason="needs Git Bash on Windows")
def test_heredoc_runs(tmp_path):
    python = sys.executable.replace("\\", "/")
    command = f"cat > made.py <<'EOF'\nprint('from heredoc')\nEOF\n\"{python}\" made.py"
    result = shell_tool.run_shell_command_tool(command, working_directory=str(tmp_path))
    assert result["stdout"].strip() == "from heredoc"
    assert (tmp_path / "made.py").is_file()


@pytest.mark.skipif(os.name != "nt", reason="Windows only")
def test_without_git_bash_windows_still_refuses(monkeypatch):
    monkeypatch.setattr(shell_tool, "git_bash", lambda: None)
    assert shell_tool.multiline_error("echo a\necho b") == shell_tool.MULTILINE_ON_WINDOWS
    assert shell_tool.multiline_error("echo a") is None


def test_git_bash_is_only_looked_for_on_windows():
    if os.name != "nt":
        assert shell_tool.git_bash() is None
    else:
        found = shell_tool.git_bash()
        assert found is None or (
            found.lower().endswith("bash.exe") and "system32" not in found.lower()
        )
