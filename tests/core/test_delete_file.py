"""delete_file: removing a file a task asks to remove, without a shell command."""

import pytest
from test_agent_loop import FakeClient, call, make_agent, text, tool_messages

from joshu.core.permissions import PermissionMode
from joshu.tools import filesystem_tools
from joshu.tools.filesystem_tools import delete_file_tool


@pytest.fixture
def workspace(tmp_path):
    filesystem_tools.set_workspace_root(tmp_path)
    yield tmp_path
    filesystem_tools._workspace_root = None


def test_bypass_deletes_and_rewind_brings_it_back(workspace):
    old = workspace / "app" / "http_old.py"
    old.parent.mkdir()
    old.write_text("def fetch(): ...\n", encoding="utf-8")
    client = FakeClient([call("delete_file", path="app/http_old.py"), text("Deleted.")])
    agent = make_agent(client, mode=PermissionMode.BYPASS)
    agent.run("then delete app/http_old.py")
    assert not old.exists()
    assert '"success": true' in tool_messages(agent.messages)[0]["content"]
    agent.checkpoints.undo()
    assert old.read_text(encoding="utf-8") == "def fetch(): ...\n"


@pytest.mark.parametrize(
    "mode, approve, kept",
    [
        (PermissionMode.DEFAULT, None, True),  # asks; no one to answer: denied
        (PermissionMode.DEFAULT, "yes", False),
        (PermissionMode.ACCEPT_EDITS, None, False),
        (PermissionMode.PLAN, None, True),
    ],
)
def test_delete_follows_the_edit_permissions(workspace, mode, approve, kept):
    from joshu.core.permissions import ApprovalChoice

    target = workspace / "notes.txt"
    target.write_text("x", encoding="utf-8")
    approver = (lambda request: ApprovalChoice.YES) if approve else None
    client = FakeClient([call("delete_file", path="notes.txt"), text("ok")])
    make_agent(client, mode=mode, approver=approver).run("delete notes.txt")
    assert target.exists() is kept


def test_protected_files_still_ask_in_bypass(workspace):
    env = workspace / ".env"
    env.write_text("KEY=1", encoding="utf-8")
    client = FakeClient([call("delete_file", path=".env"), text("ok")])
    make_agent(client, mode=PermissionMode.BYPASS).run("delete .env")
    assert env.exists()


def test_only_single_files_inside_the_workspace(workspace, tmp_path_factory):
    (workspace / "pkg").mkdir()
    outside = tmp_path_factory.mktemp("outside") / "keep.txt"
    outside.write_text("x", encoding="utf-8")
    assert "directory" in delete_file_tool("pkg")["error"]
    assert "outside workspace" in delete_file_tool(str(outside))["error"]
    assert "workspace root" in delete_file_tool(".")["error"]
    assert "not found" in delete_file_tool("missing.py")["error"]
    assert (workspace / "pkg").is_dir() and outside.exists()


def test_a_blocked_shell_delete_points_to_delete_file():
    import os

    from joshu.core.safety import assess_command_safety

    command = "del notes.txt" if os.name == "nt" else "rm notes.txt"
    report = assess_command_safety(command, sandbox_mode=True)
    assert not report.safe and "delete_file" in " ".join(report.reasons)
