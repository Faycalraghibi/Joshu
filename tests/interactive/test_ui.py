"""The terminal UI: welcome box, input area, mode cycling, tool display, approvals."""

import io
import json
from unittest.mock import MagicMock, patch

import pytest
from rich.console import Console

from joshu.core.llm_client import AssistantTurn
from joshu.core.permissions import ApprovalChoice, ApprovalRequest, PermissionManager
from joshu.ui import agent_ui
from joshu.ui.agent_ui import ConsoleAgentUI, render_diff
from joshu.ui.interactive.prompt import bottom_toolbar, prompt_message

DIFF = "--- a/x.py\n+++ b/x.py\n@@ -1,2 +1,2 @@\n def f():\n-    return 1\n+    return 2\n"


def terminal_ui():
    buffer = io.StringIO()
    console = Console(file=buffer, force_terminal=True, width=100, color_system=None)
    return ConsoleAgentUI(console), buffer


def text_of(buffer):
    return buffer.getvalue()


# ------------------------------------------------------------- agent output


def test_reply_is_rendered_as_markdown_with_bullet():
    ui, out = terminal_ui()
    ui.on_model_start()
    ui.on_text("Use **bold** and\n\n- one\n- two")
    ui.on_turn_end(AssistantTurn())
    shown = " ".join(text_of(out).split())  # spacing differs between rich versions
    assert "● Use bold and" in shown and "• one" in shown
    assert ui._live is None  # spinner stopped


def test_tool_calls_show_label_and_result():
    ui, out = terminal_ui()
    ui.on_tool_start("read_file", {"path": "a.py"})
    ui.on_tool_end("read_file", json.dumps({"total_lines": 12}), True)
    ui.on_tool_start("run_shell_command", {"command": "pytest -q"})
    ui.on_tool_end(
        "run_shell_command",
        json.dumps({"exit_code": 0, "stdout": "\n".join(f"line {i}" for i in range(7))}),
        True,
    )
    shown = text_of(out)
    assert "● Read(a.py)" in shown and "⎿  Read 12 lines" in shown
    assert "● Bash(pytest -q)" in shown and "line 3" in shown and "… +3 lines" in shown
    assert "line 5" not in shown


def test_edit_shows_counts_and_diff():
    ui, out = terminal_ui()
    ui.on_tool_start("replace", {"path": "x.py"})
    ui.on_tool_end("replace", json.dumps({"success": True, "diff": DIFF}), True)
    shown = text_of(out)
    assert "Updated x.py with 1 addition and 1 removal" in shown
    assert "-     return 1" in shown and "+     return 2" in shown


def test_todos_render_as_checklist():
    ui, out = terminal_ui()
    todos = [
        {"description": "done thing", "status": "completed"},
        {"description": "next thing", "status": "pending"},
    ]
    ui.on_tool_start("write_todos", {"todos": todos})
    ui.on_tool_end("write_todos", "{}", True)
    shown = text_of(out)
    assert "● Update Todos\n" in shown
    assert "☒ done thing" in shown and "☐ next thing" in shown


def test_failures_and_subagent_labels():
    ui, out = terminal_ui()
    ui.on_tool_start("explore › read_file", {"path": "b.py"})
    ui.on_tool_end("explore › read_file", "Error: File not found: b.py", False)
    shown = text_of(out)
    assert "● explore › Read(b.py)" in shown and "⎿  Error: File not found: b.py" in shown


def test_plain_output_without_a_terminal_streams_text():
    console = Console(file=io.StringIO(), force_terminal=False)
    ui = ConsoleAgentUI(console)
    assert not ui.rich_mode
    with patch("sys.stdout", new=io.StringIO()) as stdout:
        ui.on_text("hello")
        ui.on_turn_end(AssistantTurn(content="hello"))
    assert stdout.getvalue() == "hello\n"


def test_render_diff_numbers_lines():
    console = Console(file=io.StringIO(), width=80, color_system=None)
    console.print(render_diff(DIFF, 10))
    lines = console.file.getvalue().splitlines()
    assert lines[0].split() == ["1", "def", "f():"]
    assert lines[1].split()[:2] == ["2", "-"]


# ---------------------------------------------------------------- approvals


def approve_with(choice, feedback=None):
    ui, out = terminal_ui()
    request = ApprovalRequest("run_shell_command", {"command": "git status"}, "git status")
    with (
        patch.object(agent_ui, "_choose", return_value=choice) as chooser,
        patch.object(agent_ui, "_ask_feedback", return_value=feedback),
    ):
        result = ui.approve(request)
    return result, request, chooser, text_of(out)


def test_approval_options_and_panel():
    result, _, chooser, shown = approve_with(ApprovalChoice.YES)
    assert result == ApprovalChoice.YES
    question, options = chooser.call_args[0]
    assert question == "Do you want to run this command?"
    assert [label for _, label in options] == [
        "Yes",
        "Yes, and don't ask again for `git status` commands this session",
        "No, and tell Joshu what to do differently (esc)",
    ]
    assert "Bash command" in shown


def test_declining_with_feedback_reaches_the_model():
    manager = PermissionManager(approver=None)
    ui, _ = terminal_ui()
    manager.approver = ui.approve
    with (
        patch.object(agent_ui, "_choose", return_value=ApprovalChoice.NO),
        patch.object(agent_ui, "_ask_feedback", return_value="use npm instead"),
    ):
        decision = manager.check("run_shell_command", {"command": "yarn"}, True)
    assert not decision.allowed
    assert "They said: use npm instead" in decision.reason


def test_chained_commands_get_no_always_option():
    ui, _ = terminal_ui()
    request = ApprovalRequest("run_shell_command", {"command": "a && b"}, "a && b")
    with (
        patch.object(agent_ui, "_choose", return_value=ApprovalChoice.YES) as chooser,
        patch.object(agent_ui, "_ask_feedback"),
    ):
        ui.approve(request)
    assert len(chooser.call_args[0][1]) == 2


def test_choose_falls_back_to_typed_answers():
    options = [(ApprovalChoice.YES, "Yes"), (ApprovalChoice.NO, "No")]
    with patch("builtins.input", side_effect=["x", "2"]), patch("builtins.print"):
        assert agent_ui._choose("Allow?", options) == ApprovalChoice.NO


# --------------------------------------------------------------- input area


def test_bottom_toolbar_shows_mode_and_model():
    toolbar = "".join(text for _, text in bottom_toolbar("accept_edits", "my-model"))
    assert "⏵⏵ accept edits on (shift+tab to cycle)" in toolbar
    assert toolbar.rstrip().endswith("my-model")
    notice = "".join(text for _, text in bottom_toolbar("default", "m", "Press Ctrl+C again"))
    assert "Press Ctrl+C again" in notice
    assert prompt_message()[-1] == ("class:prompt", "> ")


@pytest.fixture
def mode():
    pytest.importorskip("prompt_toolkit")
    from joshu.ui.interactive import InteractiveMode

    with patch("joshu.ui.interactive.interactive_mode.ContextProvider"):
        yield InteractiveMode("test-model", sandbox=False, verbose=False)


def test_shift_tab_cycles_modes(mode):
    mode.config_manager.set("permission_mode", "default")
    assert mode.current_mode() == "default"
    assert mode.cycle_mode() == "accept_edits"
    assert mode.config_manager.get("permission_mode") == "accept_edits"
    assert mode.cycle_mode() == "plan" and mode.interaction_mode == "plan"
    assert mode.cycle_mode() == "default" and mode.interaction_mode == "agent"


def test_question_mark_shows_shortcuts(mode):
    mode._show_message = MagicMock()
    mode._handle_user_input("?")
    assert "shift+tab" in mode._show_message.call_args[0][0]


def test_prompt_accepts_the_input_area_options(mode):
    """The real prompt_toolkit prompt runs with our message, toolbar and placeholder."""
    from prompt_toolkit.application import create_app_session
    from prompt_toolkit.input import create_pipe_input
    from prompt_toolkit.output import DummyOutput

    from joshu.ui.interactive import interactive_mode as im

    seen = []
    mode._handle_user_input = lambda text: seen.append(text) or False
    with create_pipe_input() as pipe:
        pipe.send_text("hello\r")
        with create_app_session(input=pipe, output=DummyOutput()):
            with patch.object(im, "prompt", wraps=im.prompt):
                mode.start()
    assert seen == ["hello"]
