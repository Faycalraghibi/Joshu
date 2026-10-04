"""Command registry, the new slash commands, completion, themes and the mascot."""

import io
import json
from unittest.mock import MagicMock, patch

import pytest
from rich.console import Console

from joshu.ui import display
from joshu.ui.interactive.command_registry import COMMANDS, GROUPS, find_command
from joshu.ui.interactive.commands_extra import _latest_todos, conversation_markdown
from joshu.ui.theme import MASCOT, THEMES, current_theme

pytest.importorskip("prompt_toolkit")


@pytest.fixture
def screen():
    buffer = io.StringIO()
    original = display.console
    display.console = Console(file=buffer, width=120, color_system=None)
    yield buffer
    display.console = original


@pytest.fixture
def mode(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    from joshu.ui.interactive import InteractiveMode

    with patch("joshu.ui.interactive.interactive_mode.ContextProvider"):
        instance = InteractiveMode("test-model", sandbox=False, verbose=False)
    instance._show_message = MagicMock()
    return instance


def run(mode, command):
    return mode.command_handler.handle_slash_command(command)


# ---------------------------------------------------------------- registry


def test_every_command_has_a_handler_and_group(mode):
    for command in COMMANDS:
        assert command.group in GROUPS
        assert callable(getattr(mode.command_handler, command.method)), command.name


def test_aliases_resolve():
    assert find_command("/reset").name == "clear"
    assert find_command("quit").name == "exit"
    assert find_command("/nope") is None


def test_exit_ends_the_session(mode):
    assert run(mode, "/exit") is False
    assert run(mode, "/quit") is False


def test_clear_starts_a_new_conversation(mode):
    with patch.object(mode.command_handler, "handle_session_command", return_value=True) as new:
        assert run(mode, "/clear") is True
    new.assert_called_once_with("/session new")


def test_history_clear(mode):
    mode.prompt_history = MagicMock()
    run(mode, "/history clear")
    mode.prompt_history.clear.assert_called_once()


def test_help_lists_groups_usage_and_shortcuts(mode, screen):
    run(mode, "/help")
    shown = screen.getvalue()
    for group in GROUPS:
        assert group in shown
    assert "/rewind [n]" in shown and "/config [key [value]]" in shown
    assert "shift+tab" in shown


# ---------------------------------------------------------------- commands


def test_status_shows_model_and_mode(mode, screen):
    run(mode, "/status")
    shown = screen.getvalue()
    assert "test-model" in shown and "Mode" in shown and "Theme" in shown


def test_context_breakdown(mode, screen):
    agent = MagicMock(context_window=10000, compact_threshold=0.8)
    agent.messages = [{"role": "system", "content": "s" * 400}, {"role": "user", "content": "hi"}]
    agent.request_tools.return_value = []
    mode.agent = agent
    run(mode, "/context")
    shown = screen.getvalue()
    assert "/ 10,000 tokens" in shown and "System prompt" in shown and "8,000" in shown


def tool_message(name, arguments):
    return {
        "role": "assistant",
        "content": "",
        "tool_calls": [{"id": "1", "function": {"name": name, "arguments": json.dumps(arguments)}}],
    }


def test_todos_show_latest_list(mode, screen):
    mode.agent = MagicMock()
    mode.agent.messages = [
        tool_message("write_todos", {"todos": [{"description": "old"}]}),
        tool_message(
            "write_todos",
            {"todos": [{"description": "done", "status": "completed"}, {"description": "next"}]},
        ),
    ]
    run(mode, "/todos")
    shown = screen.getvalue()
    assert "☒ done" in shown and "☐ next" in shown and "old" not in shown
    assert _latest_todos([]) is None


def test_export_writes_markdown(mode, screen, tmp_path):
    mode.agent = MagicMock()
    mode.agent.messages = [
        {"role": "system", "content": "sys"},
        {"role": "user", "content": "fix the bug"},
        tool_message("read_file", {"path": "calc.py"}),
        {"role": "tool", "tool_call_id": "1", "content": "{}"},
        {"role": "assistant", "content": "Fixed it."},
    ]
    run(mode, "/export notes")
    text = (tmp_path / "notes.md").read_text(encoding="utf-8")
    assert "## You\n\nfix the bug" in text
    assert "- `read_file` calc.py" in text and "## Joshu\n\nFixed it." in text
    assert "sys" not in conversation_markdown(mode.agent.messages).split("\n", 1)[1]


def test_review_runs_agent_with_focus(mode):
    mode._ensure_agent = MagicMock(return_value=True)
    mode._run_agent = MagicMock(return_value=True)
    run(mode, "/review error handling")
    prompt = mode._run_agent.call_args[0][0]
    assert "git diff" in prompt and "Focus on: error handling" in prompt


def test_theme_set_and_unknown(mode, screen):
    mode.config_manager.save_config = MagicMock()
    run(mode, "/theme light")
    assert mode.config_manager.get("theme") == "light"
    assert current_theme().name == "light"
    run(mode, "/theme neon")
    assert "Unknown theme 'neon'" in screen.getvalue()
    mode.config_manager.set("theme", "dark")


def test_vim_toggle(mode, screen):
    mode.config_manager.save_config = MagicMock()
    run(mode, "/vim")
    assert mode.vim_enabled and mode.config_manager.get("vim_mode") is True
    run(mode, "/vim")
    assert not mode.vim_enabled and mode.vim_mode == "INSERT"


def test_doctor_reports_missing_key(mode, screen, monkeypatch):
    monkeypatch.delenv("NVIDIA_API_KEY", raising=False)
    mode.config_manager.set("provider", "nvidia")
    run(mode, "/doctor")
    shown = screen.getvalue()
    assert "Provider nvidia" in shown and "✗ API key" in shown


def test_doctor_checks_the_model(mode, screen, monkeypatch):
    from joshu.core.model_catalog import CheckResult

    monkeypatch.setenv("NVIDIA_API_KEY", "nvapi-test")
    mode.config_manager.set("provider", "nvidia")
    mode.config_manager.set("model", "nvidia/m1")
    with patch("joshu.core.model_catalog.check_model", return_value=CheckResult(True, True, 1.5)):
        run(mode, "/doctor")
    assert "✓ Model nvidia/m1" in screen.getvalue()


# -------------------------------------------------------------- completion


def complete(text, completer):
    from prompt_toolkit.document import Document

    return list(completer.get_completions(Document(text), None))


def test_slash_menu_has_descriptions():
    from joshu.ui.interactive.completers import get_command_completer

    completer = get_command_completer([("/deploy", "Ship it")])
    items = {c.text: c for c in complete("/re", completer)}
    assert "/rewind" in items
    assert items["/rewind"].display_meta_text == "Drop the last n requests and restore their files"
    assert items["/rewind"].display_text == "/rewind [n]"
    assert complete("/dep", completer)[0].display_meta_text == "Ship it"


def test_at_completes_project_files(tmp_path):
    from joshu.ui.interactive.completers import JoshuCompleter

    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "calc.py").write_text("x", encoding="utf-8")
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "node_modules" / "calc.js").write_text("x", encoding="utf-8")
    completer = JoshuCompleter({}, root=tmp_path)

    found = [c.text for c in complete("look at @cal", completer)]
    assert found == ["@src/calc.py"]


# ------------------------------------------------------------ look and feel


def test_themes_are_complete_and_fallback():
    for theme in THEMES.values():
        assert theme.name in THEMES
    assert current_theme("nope").name == "dark"
    assert THEMES["plain"].accent == ""


def test_welcome_box_has_mascot_and_model(screen, tmp_path):
    display.print_banner("my-model", cwd=tmp_path)
    shown = screen.getvalue()
    assert MASCOT[2].strip() in shown and "Welcome to Joshu" in shown
    assert "my-model" in shown and "Run /init" in shown


def test_activity_labels():
    from joshu.ui.agent_ui import activity_label

    assert activity_label("run_shell_command", {"command": "pytest -q"}) == "Running pytest -q"
    assert activity_label("read_file", {"path": "a.py"}) == "Reading a.py"
    assert activity_label("mcp_tool", {}) == "Running mcp_tool"


def test_bare_joshu_starts_interactive(monkeypatch):
    from joshu.ui import cli

    monkeypatch.setattr("sys.argv", ["joshu"])
    with patch.object(cli, "app") as app:
        cli.main()
    app.assert_called_once()
    assert __import__("sys").argv == ["joshu", "interactive"]


@pytest.mark.parametrize("width", [60, 100, 140])
def test_welcome_box_spans_the_terminal(tmp_path, width):
    buffer = io.StringIO()
    original = display.console
    display.console = Console(file=buffer, width=width, color_system=None)
    try:
        display.print_banner("m", cwd=tmp_path)
    finally:
        display.console = original
    top = buffer.getvalue().splitlines()[0]
    assert len(top) == width
    assert MASCOT[2].strip() in buffer.getvalue()


def test_narrow_terminal_drops_the_mascot(tmp_path):
    buffer = io.StringIO()
    original = display.console
    display.console = Console(file=buffer, width=50, color_system=None)
    try:
        display.print_banner("m", cwd=tmp_path)
    finally:
        display.console = original
    assert MASCOT[2].strip() not in buffer.getvalue()
    assert "Welcome to Joshu" in buffer.getvalue()
