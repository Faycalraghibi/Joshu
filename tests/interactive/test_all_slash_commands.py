"""
Every slash command, run through a real InteractiveMode with a fake model:
none may raise, each must return whether the session continues, and none
may fall through to "Unknown command". New commands are covered by default.
"""

import contextlib
import io
import subprocess

import pytest

pytest.importorskip("prompt_toolkit")

from joshu.core import agent as agent_module  # noqa: E402
from joshu.core.llm_client import AssistantTurn, ToolCall  # noqa: E402
from joshu.ui.interactive.command_registry import COMMANDS  # noqa: E402

# Commands that reach the network (live model lists, web search)
NETWORK = {"models", "search"}

# Extra forms worth running besides the bare command
VARIANTS = [
    "please CREATE a file",
    "/undo",
    "please CREATE a file",
    "/rewind 1",
    "/rewind x",
    "/compact focus on files",
    "/export",
    "/export sub/dir/out.md",
    "/session list",
    "/session help",
    "/session bogus",
    "/resume nope",
    "/memory add Always use tabs here",
    "/memory add --user I like short answers",
    "/memory forget always-use-tabs-here",
    "/model",
    "/permissions accept_edits",
    "/permissions bogus",
    "/permissions default",
    "/theme light",
    "/theme dark",
    "/theme bogus",
    "/output-style explanatory",
    "/output-style default",
    "/output-style bogus",
    "/sandbox bogus",
    "/statusline echo hi",
    "/statusline off",
    "/config theme",
    "/config bogus_key",
    "/config vim_mode true",
    "/config vim_mode false",
    "/config statusline echo two words",
    "/hooks add before_tool echo hi",
    "/hooks remove before_tool 1",
    "/hooks add",
    "/bashes kill nope",
    "/add-dir does/not/exist",
    "/demo",
    "/demo with a request",
    "/skills remove demo",
    "/skills add",
    "/hello Bob",
    "/pr-comments 12",
    "/init keep it short",
    "/history clear",
    "/clear",
]


class FakeClient:
    model = "fake-model"
    base_url = "http://fake"
    context_window = 128000

    def __init__(self):
        self.calls = 0

    def complete(self, messages, tools=None, **kwargs):
        self.calls += 1
        last = messages[-1]
        if last.get("role") == "user" and "CREATE" in str(last.get("content")):
            arguments = '{"path": "new.txt", "content": "made by the agent"}'
            call = ToolCall(id=f"c{self.calls}", name="write_file", arguments=arguments)
            return AssistantTurn(tool_calls=[call])
        return AssistantTurn(content="Done.", usage={"prompt_tokens": 100, "completion_tokens": 5})


@pytest.fixture
def mode(tmp_path, monkeypatch):
    project = tmp_path / "project"
    project.mkdir()
    monkeypatch.setenv("JOSHU_HOME", str(tmp_path / "home"))
    from joshu.core.config import get_config_manager

    # The test config (see conftest) has MCP off; edits run without asking
    get_config_manager().set("permission_mode", "accept_edits")
    monkeypatch.setenv("NVIDIA_API_KEY", "fake")
    monkeypatch.chdir(project)
    subprocess.run(["git", "init", "-q"], check=True)
    skill = project / ".agents" / "skills" / "demo"
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text(
        "---\nname: demo\ndescription: Demo skill\n---\nSay DEMO.", encoding="utf-8"
    )
    commands = project / ".joshu" / "commands"
    commands.mkdir(parents=True)
    (commands / "hello.md").write_text(
        "---\ndescription: Say hello\n---\nSay hello to $ARGUMENTS", encoding="utf-8"
    )
    monkeypatch.setattr(agent_module, "create_chat_client", lambda *a, **k: FakeClient())
    monkeypatch.setattr("joshu.core.llm_client.create_chat_client", lambda *a, **k: FakeClient())
    # /doctor sends a test request to the model
    monkeypatch.setattr("joshu.core.llm_client._client_for_provider", lambda *a, **k: FakeClient())
    from joshu.ui.interactive.interactive_mode import InteractiveMode

    interactive = InteractiveMode("fake-model")
    yield interactive
    if interactive.agent is not None:
        interactive.agent.end_session()


def run(mode, text):
    out = io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
        result = mode._handle_user_input(text)
    return result, out.getvalue()


def test_every_command_runs(mode):
    commands = [c for c in COMMANDS if c.name not in NETWORK and c.name != "exit"]
    # A request first, so conversation commands have something to work on
    # Back to agent mode after /plan and /ask, then the variants; ask mode last
    texts = ["hello"] + [f"/{c.name}" for c in commands] + ["/agent"] + VARIANTS
    texts += ["/ask", "a question", "/agent"]
    for text in texts:
        result, output = run(mode, text)
        assert result is True, f"{text} returned {result!r}: {output[-500:]}"
        assert "Traceback" not in output, f"{text}: {output[-1500:]}"
        assert "Unknown command" not in output, f"{text}: {output[-500:]}"
    assert run(mode, "/exit")[0] is False


def test_aliases_run(mode):
    for command in COMMANDS:
        for alias in command.aliases:
            if command.name == "exit":
                continue
            result, output = run(mode, f"/{alias}")
            assert result is True and "Unknown command" not in output, alias


def test_memory_add_saves_a_memory(mode):
    from joshu.core.auto_memory import list_memories

    _, output = run(mode, "/memory add Always use tabs here")
    assert "Saved project memory 'always-use-tabs-here'" in output
    assert [m.name for m in list_memories("project")] == ["always-use-tabs-here"]


def test_config_rejects_unknown_keys_and_takes_values_with_spaces(mode):
    from joshu.core.config import get_config_manager

    assert "Unknown setting 'them'" in run(mode, "/config them dark")[1]
    run(mode, "/config statusline echo two words")
    assert get_config_manager().get("statusline") == "echo two words"
    run(mode, "/config vim_mode true")
    assert mode.vim_enabled
    run(mode, "/config vim_mode false")


def test_export_creates_folders(mode, tmp_path):
    run(mode, "hello")
    _, output = run(mode, "/export notes/today/chat.md")
    assert "Saved the conversation" in output
    assert (tmp_path / "project" / "notes" / "today" / "chat.md").is_file()


def test_session_keeps_its_title_after_compact(mode):
    from joshu.core.sessions import list_sessions

    run(mode, "the first request")
    run(mode, "the second request")
    run(mode, "/compact")
    run(mode, "a third one")
    titles = [info.title for info in list_sessions(None)]
    assert "the first request" in titles


def test_unknown_command_says_so(mode):
    result, output = run(mode, "/definitely-not-a-command")
    assert result is True and "Unknown command" in output
