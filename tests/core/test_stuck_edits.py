"""Edits that keep a file broken, empty replies, and steps announced but not taken."""

import json

import pytest
from test_agent_loop import FakeClient, call, make_agent, text, tool_messages

from joshu.core.agent import (
    ANNOUNCED_STEP_NOTE,
    EMPTY_REPLY_NOTE,
    malformed_reply,
)
from joshu.core.config import get_config_manager
from joshu.core.diagnostics import check_file, runaway_string_hint
from joshu.core.permissions import PermissionMode
from joshu.tools import filesystem_tools

# What the benchmark's model wrote: the module docstring lost its closing quotes,
# so Python complains about line 9, far from the cause on line 1
BROKEN = '''"""Reading values out of nested JSON data with a path string.

from typing import Any

MISSING = object()


def get(data: Any, path: str, default: Any = MISSING) -> Any:
    """
    The value at `path` in `data` (nested dicts and lists).
    """
    raise NotImplementedError
'''
FIXED = BROKEN.replace("path string.\n", 'path string."""\n', 1)


def test_runaway_string_points_at_the_start(tmp_path):
    hint = runaway_string_hint(BROKEN)
    assert hint and "starts on line 1" in hint
    assert runaway_string_hint(FIXED) is None
    assert runaway_string_hint('x = """never closed\n') is not None
    path = tmp_path / "jsonpath.py"
    path.write_text(BROKEN, encoding="utf-8")
    problems = check_file(path)
    assert "SyntaxError" in problems and "starts on line 1" in problems


@pytest.fixture
def workspace(tmp_path):
    filesystem_tools.set_workspace_root(tmp_path)
    get_config_manager().set("lsp", False)
    yield tmp_path
    filesystem_tools._workspace_root = None


def write(content, call_id):
    return call("write_file", call_id=call_id, path="jsonpath.py", content=content)


def test_repeated_broken_edits_escalate(workspace):
    client = FakeClient(
        [
            write(BROKEN, "w1"),
            write(BROKEN, "w2"),
            write(FIXED, "w3"),
            write(BROKEN, "w4"),
            text("done"),
        ]
    )
    agent = make_agent(client, mode=PermissionMode.BYPASS, cwd=workspace)
    agent.run("implement get")
    outputs = [m["content"] for m in tool_messages(agent.messages)]
    assert "now has problems" in outputs[0] and "edits in a row" not in outputs[0]
    assert "left broken by 2 edits in a row" in outputs[1] and "replace" in outputs[1]
    assert '    1: """Reading values' in outputs[1]  # the numbered lines around the cause
    assert (
        "problems" not in json.loads(outputs[2]).get("message", "") and "problems" not in outputs[2]
    )
    assert "edits in a row" not in outputs[3]  # a fixed file starts the count again


@pytest.mark.parametrize(
    "reply, changed, note",
    [
        ("", True, EMPTY_REPLY_NOTE),
        ("   ", False, EMPTY_REPLY_NOTE),
        ("Let me read the files to understand the structure better.", False, ANNOUNCED_STEP_NOTE),
        ("I'll start by listing the directory:", False, ANNOUNCED_STEP_NOTE),
        ("Let me read the files.", True, None),  # it already did work: a real (odd) answer
        ("Done. Let me know if you want the tests too.", False, None),
        ("The function is in app/http.py; it retries three times.", False, None),
    ],
)
def test_reply_checks(reply, changed, note):
    assert malformed_reply(reply, False, changed) == note


def test_announced_step_is_sent_back(workspace):
    get_config_manager().set("retry_broken_replies", True)
    client = FakeClient([text("Let me read the files first."), text("Read them; it's fine.")])
    response = make_agent(client, cwd=workspace).run("check the project")
    assert response.text == "Read them; it's fine."
    assert client.requests[1][-1]["content"] == ANNOUNCED_STEP_NOTE


def self_check_notes(client):
    from joshu.core.agent import SELF_CHECK_NOTE

    return [m for r in client.requests for m in r if m.get("content") == SELF_CHECK_NOTE]


def edit_app():
    return call("write_file", call_id="w1", path="app.py", content="X = 1\n")


def test_no_tests_asks_for_a_check_once(workspace):
    get_config_manager().set("verify_command", "")  # find it: this project has none
    client = FakeClient([edit_app(), text("Done."), text("Checked, done.")])
    response = make_agent(client, mode=PermissionMode.BYPASS, cwd=workspace).run("add X")
    assert response.text == "Checked, done." and len(self_check_notes(client)) == 1


def test_no_check_note_after_running_something(workspace):
    get_config_manager().set("verify_command", "")
    run_it = call("run_shell_command", call_id="s1", command="python app.py")
    client = FakeClient([edit_app(), run_it, text("Done.")])
    assert (
        make_agent(client, mode=PermissionMode.BYPASS, cwd=workspace).run("add X").text == "Done."
    )
    assert self_check_notes(client) == []


def test_no_check_note_when_nothing_can_run(workspace):
    get_config_manager().set("verify_command", "")
    client = FakeClient([edit_app(), text("Done.")])
    # accept_edits with nobody to approve: commands can't run, so don't ask
    agent = make_agent(client, mode=PermissionMode.ACCEPT_EDITS, cwd=workspace)
    assert agent.run("add X").text == "Done." and self_check_notes(client) == []
