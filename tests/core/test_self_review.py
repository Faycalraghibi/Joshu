"""Before finishing a request that changed something, the agent checks its work once."""

import json

from joshu.core.agent import SELF_REVIEW_NOTE, Agent
from joshu.core.llm_client import AssistantTurn, ToolCall
from joshu.core.permissions import PermissionManager, PermissionMode
from joshu.tools import filesystem_tools


class Script:
    model = "fake"

    def __init__(self, turns):
        self.turns = list(turns)
        self.requests = []

    def complete(self, messages, tools=None, **kwargs):
        self.requests.append([dict(m) for m in messages])
        return self.turns.pop(0)


def write(path, content, call_id="c1"):
    return AssistantTurn(
        tool_calls=[
            ToolCall(
                id=call_id,
                name="write_file",
                arguments=json.dumps({"path": path, "content": content}),
            )
        ]
    )


def say(text):
    return AssistantTurn(content=text, finish_reason="stop")


def make(client, monkeypatch, tmp_path, enabled=True):
    from joshu.core.config import get_config_manager

    monkeypatch.chdir(tmp_path)
    filesystem_tools.set_workspace_root(tmp_path)
    get_config_manager().set("self_review", enabled)
    return Agent(permissions=PermissionManager(PermissionMode.BYPASS), client=client, persist=False)


def test_review_once_after_an_edit(tmp_path, monkeypatch):
    client = Script([write("a.txt", "x"), say("done"), say("checked: all done")])
    response = make(client, monkeypatch, tmp_path).run("create a.txt")
    assert response.text == "checked: all done"
    assert client.requests[2][-1] == {"role": "user", "content": SELF_REVIEW_NOTE}
    assert len(client.requests) == 3  # one review, not a loop


def test_review_can_lead_to_more_work(tmp_path, monkeypatch):
    client = Script([write("a.txt", "x"), say("done"), write("b.txt", "y", "c2"), say("now done")])
    response = make(client, monkeypatch, tmp_path).run("create a.txt and b.txt")
    assert response.text == "now done" and (tmp_path / "b.txt").exists()


def test_no_review_without_changes_or_when_off(tmp_path, monkeypatch):
    client = Script([say("hello")])
    assert make(client, monkeypatch, tmp_path).run("hi").text == "hello"
    client = Script([write("a.txt", "x"), say("done")])
    assert make(client, monkeypatch, tmp_path, enabled=False).run("create").text == "done"
