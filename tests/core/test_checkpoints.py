"""Tests for undoing the agent's file edits."""

import json

import pytest

from joshu.core.agent import Agent
from joshu.core.checkpoints import CheckpointStore
from joshu.core.llm_client import AssistantTurn, ToolCall
from joshu.core.permissions import PermissionManager, PermissionMode
from joshu.tools import filesystem_tools


class FakeClient:
    model = "fake"

    def __init__(self, turns):
        self.turns = list(turns)
        self.requests = []

    def complete(self, messages, tools=None, **kwargs):
        self.requests.append([dict(m) for m in messages])
        return self.turns.pop(0)


def call(name, call_id="c1", **arguments):
    return AssistantTurn(tool_calls=[ToolCall(call_id, name, json.dumps(arguments))])


def text(content):
    return AssistantTurn(content=content)


@pytest.fixture
def workspace(tmp_path):
    filesystem_tools.set_workspace_root(tmp_path)
    yield tmp_path
    filesystem_tools._workspace_root = None


def make_agent(client, workspace):
    return Agent(
        client=client,
        permissions=PermissionManager(PermissionMode.ACCEPT_EDITS),
        system_prompt="test",
        cwd=workspace,
    )


def test_undo_restores_edited_file_and_deletes_created_one(workspace):
    (workspace / "a.py").write_text("x = 1\n", encoding="utf-8")
    client = FakeClient(
        [
            call("replace", path="a.py", old_string="x = 1", new_string="x = 2"),
            call("write_file", call_id="c2", path="new.py", content="print(1)\n"),
            text("done"),
        ]
    )
    agent = make_agent(client, workspace)
    agent.run("change things")
    assert (workspace / "a.py").read_text(encoding="utf-8") == "x = 2\n"
    assert (workspace / "new.py").exists()

    checkpoint = agent.undo()

    assert checkpoint.prompt == "change things"
    assert (workspace / "a.py").read_text(encoding="utf-8") == "x = 1\n"
    assert not (workspace / "new.py").exists()
    assert agent.undo() is None


def test_undo_reverts_only_the_latest_editing_request(workspace):
    target = workspace / "a.txt"
    target.write_text("v1", encoding="utf-8")
    client = FakeClient(
        [
            call("write_file", path="a.txt", content="v2"),
            text("ok"),
            text("just chatting"),  # a request without edits makes no checkpoint
            call("write_file", call_id="c3", path="a.txt", content="v3"),
            text("ok"),
        ]
    )
    agent = make_agent(client, workspace)
    agent.run("first")
    agent.run("hello")
    agent.run("second")

    agent.undo()
    assert target.read_text(encoding="utf-8") == "v2"
    agent.undo()
    assert target.read_text(encoding="utf-8") == "v1"


def test_file_is_snapshotted_once_per_request(workspace):
    target = workspace / "a.txt"
    target.write_text("original", encoding="utf-8")
    client = FakeClient(
        [
            call("write_file", path="a.txt", content="one"),
            call("write_file", call_id="c2", path="a.txt", content="two"),
            text("ok"),
        ]
    )
    agent = make_agent(client, workspace)
    agent.run("rewrite twice")

    agent.undo()
    assert target.read_text(encoding="utf-8") == "original"


def test_model_is_told_about_the_undo(workspace):
    client = FakeClient(
        [call("write_file", path="a.txt", content="x"), text("ok"), text("understood")]
    )
    agent = make_agent(client, workspace)
    agent.run("create a.txt")
    agent.undo()
    agent.run("what now?")

    last_user = [m for m in client.requests[-1] if m["role"] == "user"][-1]["content"]
    assert "undid your file changes" in last_user and last_user.endswith("what now?")


def test_denied_edit_creates_no_checkpoint(workspace):
    client = FakeClient([call("write_file", path="a.txt", content="x"), text("ok")])
    agent = Agent(
        client=client,
        permissions=PermissionManager(PermissionMode.PLAN),
        system_prompt="test",
        cwd=workspace,
    )
    agent.run("create")
    assert agent.undo() is None


def test_store_handles_binary_content(tmp_path):
    path = tmp_path / "blob.bin"
    path.write_bytes(b"\x00\xffdata")
    store = CheckpointStore()
    store.begin("edit blob")
    store.snapshot(path)
    path.write_bytes(b"changed")

    store.undo()
    assert path.read_bytes() == b"\x00\xffdata"
