"""/add-dir, /bashes, /hooks, /output-style, /statusline, /sandbox, /terminal-setup,
/release-notes, /security-review, /pr-comments, and the pieces behind them."""

import io
import sys
import time
from unittest.mock import MagicMock, patch

import pytest
from rich.console import Console

from joshu.tools import filesystem_tools, shell_tool
from joshu.ui import display

pytest.importorskip("prompt_toolkit")


@pytest.fixture
def screen():
    buffer = io.StringIO()
    original = display.console
    display.console = Console(file=buffer, width=140, color_system=None)
    yield buffer
    display.console = original


@pytest.fixture
def mode(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    from joshu.ui.interactive import InteractiveMode

    with patch("joshu.ui.interactive.interactive_mode.ContextProvider"):
        instance = InteractiveMode("test-model", sandbox=False, verbose=False)
    instance._show_message = MagicMock()
    instance.config_manager.save_config = MagicMock()
    return instance


def run(mode, command):
    return mode.command_handler.handle_slash_command(command)


# ------------------------------------------------------------------ add-dir


def test_add_dir_extends_file_tools(mode, screen, tmp_path):
    workspace = tmp_path / "project"
    other = tmp_path / "shared"
    workspace.mkdir()
    other.mkdir()
    (other / "notes.txt").write_text("hi", encoding="utf-8")
    filesystem_tools.set_workspace_root(workspace)
    mode.agent = MagicMock(_pending_notes=[])
    mode._ensure_agent = MagicMock(return_value=True)
    try:
        with pytest.raises(ValueError):
            filesystem_tools.resolve_path(str(other / "notes.txt"))
        run(mode, f"/add-dir {other}")
        assert filesystem_tools.resolve_path(str(other / "notes.txt")) == other / "notes.txt"
        assert str(other) in mode.agent._pending_notes[0]
        with pytest.raises(ValueError):
            filesystem_tools.resolve_path(str(tmp_path / "elsewhere.txt"))
    finally:
        filesystem_tools._extra_dirs.clear()
        filesystem_tools._workspace_root = None


def test_add_dir_rejects_missing_directory(mode, screen, tmp_path):
    run(mode, f"/add-dir {tmp_path / 'nope'}")
    assert "Not a directory" in screen.getvalue()


# ------------------------------------------------------------------- bashes


def test_background_output_is_readable_while_running(tmp_path):
    script = tmp_path / "talk.py"
    script.write_text(
        "import time\nprint('first', flush=True)\ntime.sleep(5)\nprint('second')\n",
        encoding="utf-8",
    )
    started = shell_tool.start_background_process(f'"{sys.executable}" "{script}"')
    process_id = started["process_id"]
    try:
        output = ""
        for _ in range(50):
            output += shell_tool.bash_output_tool(process_id)["output"]
            if "first" in output:
                break
            time.sleep(0.1)
        status = shell_tool.bash_output_tool(process_id)
        assert "first" in output and status["status"] == "running"
        assert status["output"] == ""  # only new output
    finally:
        assert shell_tool.kill_bash_tool(process_id)["success"]


def test_bashes_lists_and_kills(mode, screen):
    started = shell_tool.start_background_process(
        f'"{sys.executable}" -c "import time; time.sleep(30)"'
    )
    process_id = started["process_id"]
    try:
        run(mode, "/bashes")
        assert process_id in screen.getvalue() and "running" in screen.getvalue()
    finally:
        run(mode, f"/bashes kill {process_id}")
    assert "terminated" in screen.getvalue() or "killed" in screen.getvalue()
    assert all(p.process_id != process_id for p in shell_tool.list_background_processes())


# -------------------------------------------------------------------- hooks


def test_hooks_add_list_remove(mode, screen):
    run(mode, "/hooks add before_tool python audit.py")
    assert mode.config_manager.get("hooks") == {"before_tool": ["python audit.py"]}
    run(mode, "/hooks")
    assert "1. python audit.py" in screen.getvalue()
    run(mode, "/hooks remove before_tool 1")
    assert mode.config_manager.get("hooks") == {}
    run(mode, "/hooks add nonsense x")
    assert "Usage" in screen.getvalue()


# ------------------------------------------------------------- output style


def test_output_style_changes_system_prompt(screen, tmp_path, monkeypatch):
    from joshu.core.agent import Agent
    from joshu.core.config import get_config_manager
    from joshu.core.permissions import PermissionManager

    monkeypatch.chdir(tmp_path)
    agent = Agent(client=MagicMock(model="m", context_window=None), permissions=PermissionManager())
    assert "Output style: concise" not in agent.messages[0]["content"]

    from joshu.ui.interactive import InteractiveMode

    with patch("joshu.ui.interactive.interactive_mode.ContextProvider"):
        mode = InteractiveMode("m")
    mode.config_manager.save_config = MagicMock()
    mode.agent = agent
    run(mode, "/output-style concise")
    assert "Output style: concise" in agent.messages[0]["content"]
    run(mode, "/output-style shouty")
    assert "Unknown style 'shouty'" in screen.getvalue()
    get_config_manager().set("output_style", "default")


def test_custom_output_style(tmp_path, monkeypatch):
    from joshu.core.output_styles import available_styles, style_instructions

    monkeypatch.chdir(tmp_path)
    folder = tmp_path / ".joshu" / "output-styles"
    folder.mkdir(parents=True)
    (folder / "pirate.md").write_text("description: Arr\nTalk like a pirate.", encoding="utf-8")
    assert available_styles()["pirate"].description == "Arr"
    assert style_instructions("pirate") == "Talk like a pirate."
    assert style_instructions("default") == ""


# --------------------------------------------------------------- statusline


def test_statusline_runs_command_with_context(mode, screen):
    command = f"\"{sys.executable}\" -c \"import json,sys; d=json.load(sys.stdin); print(d['model'] + ' | ok')\""
    run(mode, f"/statusline {command}")
    assert mode.config_manager.get("statusline") == command
    assert mode.status_text() == "test-model | ok"

    from joshu.ui.interactive.prompt import bottom_toolbar

    toolbar = "".join(text for _, text in bottom_toolbar("default", "m", "", "test-model | ok"))
    assert toolbar.rstrip().endswith("test-model | ok")

    run(mode, "/statusline off")
    assert mode.status_text() == ""


def test_statusline_failure_is_blank():
    from joshu.ui.interactive.statusline import run_statusline

    assert run_statusline("definitely-not-a-command-xyz", {}) == ""


# ------------------------------------------------------------------ sandbox


def test_sandbox_show_and_set(mode, screen):
    run(mode, "/sandbox")
    assert "Shell sandbox: off" in screen.getvalue() and "docker" in screen.getvalue()
    run(mode, "/sandbox wobbly")
    assert "Unknown mode" in screen.getvalue()
    run(mode, "/sandbox off")
    assert mode.config_manager.get("shell_sandbox")["mode"] == "off"


# ------------------------------------------------------- terminal & release


@pytest.mark.parametrize(
    "env, expected",
    [
        ({"WT_SESSION": "1"}, "Windows Terminal"),
        ({"TERM_PROGRAM": "vscode"}, "VS Code"),
        ({"TERM_PROGRAM": "iTerm.app"}, "iTerm2"),
    ],
)
def test_terminal_setup_instructions(mode, screen, monkeypatch, env, expected):
    monkeypatch.delenv("WT_SESSION", raising=False)
    monkeypatch.delenv("TERM_PROGRAM", raising=False)
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    run(mode, "/terminal-setup")
    assert expected in screen.getvalue() and "Alt+Enter" in screen.getvalue()


def test_release_notes_from_changelog(mode, screen):
    run(mode, "/release-notes")
    shown = screen.getvalue()
    assert "Joshu" in shown and ("Unreleased" in shown or "github.com" in shown)


# ------------------------------------------------------------------ reviews


def test_security_review_and_pr_comments_prompts(mode, screen):
    mode._ensure_agent = MagicMock(return_value=True)
    mode._run_agent = MagicMock(return_value=True)
    run(mode, "/security-review auth")
    prompt = mode._run_agent.call_args[0][0]
    assert "security review" in prompt and "Focus on: auth" in prompt

    run(mode, "/pr-comments 42")
    prompt = mode._run_agent.call_args[0][0]
    assert "pull request #42" in prompt and "gh pr view 42 --json" in prompt

    run(mode, "/pr-comments")
    assert "the pull request for the current branch" in mode._run_agent.call_args[0][0]

    run(mode, "/pr-comments abc")
    assert "Usage: /pr-comments" in screen.getvalue()


# --------------------------------------------------------------- new lines


def test_backslash_enter_inserts_newline(mode):
    from prompt_toolkit.application import create_app_session
    from prompt_toolkit.input import create_pipe_input
    from prompt_toolkit.output import DummyOutput

    seen = []
    mode._handle_user_input = lambda text: seen.append(text) or False
    with create_pipe_input() as pipe:
        pipe.send_text("first\\\rsecond\r")
        with create_app_session(input=pipe, output=DummyOutput()):
            mode.start()
    assert seen == ["first\nsecond"]


# ------------------------------------------------------------------- plugin


def test_plugin_slash_command_lists_and_explains(mode, screen, tmp_path, monkeypatch):
    monkeypatch.setenv("JOSHU_HOME", str(tmp_path / "home"))
    run(mode, "/plugin")
    assert "No plugins" in screen.getvalue()
    run(mode, "/plugins marketplace list")
    assert "No marketplaces" in screen.getvalue()
    run(mode, "/plugin marketplace add")
    assert "Usage: /plugin" in screen.getvalue()
