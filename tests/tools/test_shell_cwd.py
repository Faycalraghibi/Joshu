"""Shell commands run in the agent's workspace, not the process's current directory."""

import sys

from joshu.tools import filesystem_tools
from joshu.tools.shell_tool import run_shell_command_tool


def test_commands_run_in_the_workspace_root(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    filesystem_tools.set_workspace_root(project)
    try:
        result = run_shell_command_tool(f'"{sys.executable}" -c "import os; print(os.getcwd())"')
        assert result["stdout"].strip() == str(project.resolve())
        (project / "sub").mkdir()
        result = run_shell_command_tool(
            f'"{sys.executable}" -c "import os; print(os.getcwd())"', working_directory="sub"
        )
        assert result["stdout"].strip() == str(project.resolve() / "sub")
    finally:
        filesystem_tools._workspace_root = None
