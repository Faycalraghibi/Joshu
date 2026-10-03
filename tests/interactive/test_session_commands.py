"""Tests for the /session commands, which manage saved agent sessions."""

from unittest.mock import MagicMock

import pytest

from joshu.core.agent import Agent
from joshu.core.llm_client import AssistantTurn
from joshu.core.permissions import PermissionManager
from joshu.core.sessions import list_sessions, load_session
from joshu.ui.interactive.commands import CommandHandler


class FakeClient:
    model = "fake"

    def complete(self, messages, tools=None, **kwargs):
        return AssistantTurn(content="ok")


@pytest.fixture
def handler(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    agent = Agent(
        client=FakeClient(),
        permissions=PermissionManager(),
        system_prompt="s",
        cwd=tmp_path,
        persist=True,
    )
    mode = MagicMock()
    mode.agent = agent
    mode._show_message = MagicMock()

    def resume(session_id=None):
        agent.restore(load_session(session_id))
        return True

    mode.resume_session = MagicMock(side_effect=resume)
    return CommandHandler(mode), mode, agent


def shown(mode):
    return "\n".join(str(c.args[0]) for c in mode._show_message.call_args_list)


def test_session_shows_current_id(handler):
    commands, mode, agent = handler
    commands.handle_slash_command("/session")
    assert agent.session_id in shown(mode)


def test_session_new_list_switch_delete(handler, tmp_path):
    commands, mode, agent = handler
    agent.run("first conversation")
    first = agent.session_id

    commands.handle_slash_command("/session new")
    assert agent.session_id != first
    agent.run("second conversation")

    commands.handle_slash_command("/session list")
    listing = shown(mode)
    assert "first conversation" in listing and "second conversation" in listing

    commands.handle_slash_command(f"/session switch {first[:6]}")
    assert agent.session_id == first

    commands.handle_slash_command(f"/session delete {first}")
    assert "current session" in shown(mode)  # refuses to delete the active one

    second = [s.id for s in list_sessions(tmp_path) if s.id != first][0]
    commands.handle_slash_command(f"/session delete {second}")
    assert {s.id for s in list_sessions(tmp_path)} == {first}


def test_reset_and_new_session_are_aliases(handler):
    commands, mode, agent = handler
    before = agent.session_id
    commands.handle_slash_command("/reset")
    after_reset = agent.session_id
    commands.handle_slash_command("/new-session")
    assert len({before, after_reset, agent.session_id}) == 3
