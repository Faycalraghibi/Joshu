"""/btw side questions (also while a task runs) and running sub-agents yourself."""

import io
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from rich.console import Console

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "core"))
from test_agent_loop import FakeClient, call, make_agent, text  # noqa: E402

from joshu.core.agent import SIDE_QUESTION_NOTE, _answerable  # noqa: E402
from joshu.core.llm_client import AssistantTurn  # noqa: E402
from joshu.ui import key_listener  # noqa: E402
from joshu.ui.agent_ui import ConsoleAgentUI, _Working  # noqa: E402
from joshu.ui.interactive.interactive_mode import side_question_text  # noqa: E402

pytest.importorskip("prompt_toolkit")


def test_side_question_text():
    assert side_question_text("/btw what is a TTL?") == "what is a TTL?"
    assert side_question_text("  /BTW  why?  ") == "why?"
    assert side_question_text("/btw") is None
    assert side_question_text("fix the bug") is None


def test_enter_on_btw_is_handled_and_other_text_waits():
    asked = []
    listener = key_listener.KeyListener(on_submit=lambda line: asked.append(line) or True)
    for key in "/btw hi\r":
        listener._add(key)
    assert asked == ["/btw hi"] and listener.typed == ""
    plain = key_listener.KeyListener(on_submit=lambda line: False)
    for key in "next task\r":
        plain._add(key)
    assert plain.typed == "next task"  # kept for the next prompt


def test_typed_text_shows_under_the_working_line():
    console = Console(file=io.StringIO(), width=100, color_system=None)
    listener = key_listener.KeyListener()
    for key in "/btw why":
        listener._add(key)
    with patch.object(key_listener, "_active", listener):
        console.print(_Working("Thinking"))
    shown = console.file.getvalue()
    assert "› /btw why" in shown and "enter asks it now" in shown


def test_side_question_leaves_the_conversation_alone(tmp_path):
    client = FakeClient([text("first answer"), AssistantTurn(content="A TTL is a lifetime.")])
    agent = make_agent(client, cwd=tmp_path)
    agent.run("hello")
    before = [dict(m) for m in agent.messages]
    assert agent.side_question("what is a TTL?") == "A TTL is a lifetime."
    assert agent.messages == before
    asked = client.requests[-1]
    assert asked[-1]["content"] == SIDE_QUESTION_NOTE + "what is a TTL?"
    assert client.tools_offered[-1] is None  # no tools for a side question


def test_answerable_drops_a_tool_call_still_running():
    messages = [
        {"role": "user", "content": "go"},
        {"role": "assistant", "content": "", "tool_calls": [{"id": "a", "function": {}}]},
        {"role": "tool", "tool_call_id": "a", "content": "ok"},
        {"role": "assistant", "content": "", "tool_calls": [{"id": "b", "function": {}}]},
    ]
    assert _answerable(messages) == messages[:3]
    assert _answerable(messages[:3]) == messages[:3]


def test_running_a_sub_agent_yourself(tmp_path):
    from joshu.tools import filesystem_tools

    filesystem_tools.set_workspace_root(tmp_path)
    try:
        (tmp_path / "a.py").write_text("x = 1\n", encoding="utf-8")
        client = FakeClient([call("read_file", path="a.py"), text("a.py sets x to 1.")])
        agent = make_agent(client, cwd=tmp_path)
        answer = agent.run_subagent("research", "what does a.py do?")
        assert answer == "a.py sets x to 1."
        assert (
            agent.messages[-2]["content"] == "[I ran the research sub-agent on: what does a.py do?]"
        )
        assert "a.py sets x to 1." in agent.messages[-1]["content"]
        assert agent.run_subagent("nobody", "x").startswith("Error: unknown agent")
    finally:
        filesystem_tools._workspace_root = None


@pytest.fixture
def mode(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    from joshu.ui.interactive import InteractiveMode

    with patch("joshu.ui.interactive.interactive_mode.ContextProvider"):
        instance = InteractiveMode("test-model", sandbox=False, verbose=False)
    instance._show_message = MagicMock()
    return instance


def shown(mode):
    return " ".join(str(c.args[0]) for c in mode._show_message.call_args_list)


def test_agents_list_and_new(mode, tmp_path):
    handler = mode.command_handler
    handler.handle_slash_command("/agents")
    assert "research" in shown(mode) and "editor" in shown(mode) and "/agents new" in shown(mode)
    handler.handle_slash_command("/agents new reviewer Reviews diffs for bugs")
    path = tmp_path / ".joshu" / "agents" / "reviewer.md"
    assert path.is_file() and "description: Reviews diffs for bugs" in path.read_text()
    handler.handle_slash_command("/agents")
    assert "reviewer" in shown(mode)
    handler.handle_slash_command("/agents new 9bad name")
    assert "Usage: /agents new" in shown(mode)
    handler.handle_slash_command("/subagent")
    assert "Usage: /subagent <name> <task>" in shown(mode)


def test_btw_slash_command(mode):
    agent = MagicMock()
    agent.side_question.return_value = "Because of caching."
    mode.agent = agent
    mode._ensure_agent = MagicMock(return_value=True)
    mode.agent_ui = ConsoleAgentUI(Console(file=io.StringIO(), width=100, color_system=None))
    mode.command_handler.handle_slash_command("/btw why is it slow?")
    agent.side_question.assert_called_once_with("why is it slow?")
    output = mode.agent_ui.console.file.getvalue()
    assert "btw" in output and "Because of caching." in output
