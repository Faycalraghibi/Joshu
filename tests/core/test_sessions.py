"""Tests for saving and resuming agent sessions."""

import json
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from joshu.core.agent import Agent
from joshu.core.llm_client import AssistantTurn, ToolCall
from joshu.core.permissions import PermissionManager, PermissionMode
from joshu.core.sessions import (
    SessionError,
    latest_session,
    list_sessions,
    load_session,
    sessions_dir,
)


class FakeClient:
    model = "fake-model"

    def __init__(self, turns):
        self.turns = list(turns)
        self.requests = []

    def complete(self, messages, tools=None, **kwargs):
        self.requests.append([dict(m) for m in messages])
        turn = self.turns.pop(0)
        if isinstance(turn, BaseException):
            raise turn
        return turn


def text(content):
    return AssistantTurn(content=content)


def make_agent(client, cwd, persist=True, session_id=None):
    return Agent(
        client=client,
        permissions=PermissionManager(PermissionMode.DEFAULT),
        system_prompt="system",
        cwd=cwd,
        persist=persist,
        session_id=session_id,
    )


def test_run_saves_session_without_system_prompt(tmp_path):
    agent = make_agent(FakeClient([text("hi there")]), tmp_path)
    agent.run("hello   world")

    data = load_session(agent.session_id)
    assert data["title"] == "hello world"
    assert data["cwd"] == str(tmp_path)
    assert data["model"] == "fake-model"
    assert [m["role"] for m in data["messages"]] == ["user", "assistant"]


def test_not_saved_without_persist(tmp_path):
    make_agent(FakeClient([text("x")]), tmp_path, persist=False).run("hi")
    assert not sessions_dir().exists() or not list(sessions_dir().glob("*.json"))


def test_restore_continues_the_conversation(tmp_path):
    first = make_agent(FakeClient([text("4")]), tmp_path)
    first.run("what is 2+2?")

    client = FakeClient([text("8")])
    second = make_agent(client, tmp_path)
    second.restore(load_session(first.session_id[:6]))  # a prefix is enough
    second.run("and doubled?")

    sent = client.requests[0]
    assert sent[0] == {"role": "system", "content": "system"}
    assert [m["content"] for m in sent[1:]] == ["what is 2+2?", "4", "and doubled?"]
    assert second.session_id == first.session_id
    assert len(load_session(first.session_id)["messages"]) == 4


def test_interrupted_run_is_saved(tmp_path):
    agent = make_agent(FakeClient([KeyboardInterrupt()]), tmp_path)
    with pytest.raises(KeyboardInterrupt):
        agent.run("long task")
    assert load_session(agent.session_id)["messages"][0]["content"] == "long task"


def test_list_and_latest_filter_by_directory(tmp_path):
    here, elsewhere = tmp_path / "here", tmp_path / "elsewhere"
    here.mkdir()
    elsewhere.mkdir()
    make_agent(FakeClient([text("a")]), here, session_id="aaa111").run("one")
    make_agent(FakeClient([text("b")]), elsewhere, session_id="bbb222").run("two")
    make_agent(FakeClient([text("c")]), here, session_id="ccc333").run("three")

    # Timestamps have one-second resolution, so only membership is checked
    assert {s.id for s in list_sessions(here)} == {"aaa111", "ccc333"}
    assert len(list_sessions()) == 3
    assert latest_session(elsewhere).id == "bbb222"


def test_unknown_and_ambiguous_ids(tmp_path):
    make_agent(FakeClient([text("a")]), tmp_path, session_id="abc111").run("one")
    make_agent(FakeClient([text("b")]), tmp_path, session_id="abc222").run("two")

    with pytest.raises(SessionError, match="No saved session"):
        load_session("zzz")
    with pytest.raises(SessionError, match="matches several"):
        load_session("abc")


def test_subagent_is_never_saved(tmp_path):
    client = FakeClient(
        [
            AssistantTurn(
                tool_calls=[
                    ToolCall("t1", "task", json.dumps({"description": "d", "prompt": "look"}))
                ]
            ),
            text("sub answer"),
            text("parent answer"),
        ]
    )
    agent = make_agent(client, tmp_path, session_id="parent1")
    agent.run("delegate")

    assert {p.stem for p in sessions_dir().glob("*.json")} == {"parent1"}


# ---------------------------------------------------------------------- CLI


def _invoke(args, client):
    from joshu.ui.cli import app

    with patch("joshu.core.agent.create_chat_client", return_value=client):
        return CliRunner().invoke(app, args)


def test_cli_resume_and_continue(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = _invoke(["run", "--output-format", "json", "remember 7"], FakeClient([text("ok")]))
    session_id = json.loads(result.stdout.strip().splitlines()[-1])["session_id"]

    client = FakeClient([text("7")])
    result = _invoke(["run", "-p", "--resume", session_id, "what number?"], client)
    assert result.exit_code == 0
    assert [m["content"] for m in client.requests[0][1:]][:2] == ["remember 7", "ok"]

    client = FakeClient([text("still 7")])
    _invoke(["run", "-p", "--continue", "again?"], client)
    assert len(client.requests[0]) == 6  # system + 4 earlier messages + new prompt


def test_cli_resume_unknown_session_fails(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = _invoke(["run", "-p", "--resume", "nope", "hi"], FakeClient([]))
    assert result.exit_code == 1


def test_cli_sessions_lists_this_directory(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _invoke(["run", "-p", "list me please"], FakeClient([text("ok")]))

    result = _invoke(["sessions"], FakeClient([]))
    assert result.exit_code == 0 and "list me please" in result.stdout


# ------------------------------------------------- single session store


def test_reset_starts_a_new_session_and_keeps_the_old_one(tmp_path):
    agent = make_agent(FakeClient([text("a"), text("b")]), tmp_path, session_id="first1")
    agent.run("one")
    agent.reset()
    agent.run("two")

    assert agent.session_id != "first1"
    assert [m["content"] for m in load_session("first1")["messages"]] == ["one", "a"]
    assert [m["content"] for m in load_session(agent.session_id)["messages"]] == ["two", "b"]


def test_delete_session(tmp_path):
    from joshu.core.sessions import delete_session

    make_agent(FakeClient([text("a")]), tmp_path, session_id="gone12").run("x")
    assert delete_session("gone") == "gone12"
    with pytest.raises(SessionError):
        load_session("gone12")


def test_recent_prompts_newest_last_without_notes(tmp_path):
    from joshu.core.sessions import recent_prompts

    agent = make_agent(FakeClient([text("a"), text("b"), text("c")]), tmp_path, session_id="s1")
    agent.run("first")
    agent._pending_notes.append("[Note: something happened.]")
    agent.run("second")
    agent.run("third")

    assert [text for _, text in recent_prompts(tmp_path, limit=2)] == ["second", "third"]


def test_nothing_is_written_to_the_working_directory(tmp_path, monkeypatch):
    from joshu.core.context_provider import ContextProvider
    from joshu.core.paths import joshu_home

    project = tmp_path / "project"
    project.mkdir()
    monkeypatch.chdir(project)
    provider = ContextProvider()
    provider.add_to_history("user", "hello")
    provider.new_session()

    assert list(project.iterdir()) == []
    assert (joshu_home() / "data.json").exists()


def test_saved_after_each_tool_round_not_only_at_the_end(tmp_path):
    # A killed process (benchmark timeout, crash) never reaches the final save
    seen = []

    class Snapshot(FakeClient):
        def complete(self, messages, tools=None, **kwargs):
            if self.requests:
                seen.append([m["role"] for m in load_session(agent.session_id)["messages"]])
            return super().complete(messages, tools, **kwargs)

    call = ToolCall(id="c1", name="list_directory", arguments=json.dumps({"path": "."}))
    agent = make_agent(Snapshot([AssistantTurn(tool_calls=[call]), text("done")]), tmp_path)
    agent.run("look around")
    assert seen == [["user", "assistant", "tool"]]
