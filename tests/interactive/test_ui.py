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


def test_finished_blocks_print_while_the_reply_streams():
    ui, out = terminal_ui()
    # Only what is printed for good; the live area is redrawn and then erased
    ui._live = MagicMock()
    ui.on_model_start()
    ui.on_text("First paragraph.\n\nSecond ")
    # The finished paragraph is on screen before the turn ends
    assert "● First paragraph." in text_of(out)
    assert "Second" not in text_of(out)
    ui.on_text("paragraph.")
    ui.on_turn_end(AssistantTurn())
    shown = text_of(out)
    assert shown.count("●") == 1  # one bullet for the whole reply
    assert "  Second paragraph." in shown


def test_emoji_with_variation_selector_does_not_overflow_lines():
    # "➡️" is drawn two cells wide but measured as one: lines padded to the
    # full width would wrap. Without the selector it is one cell everywhere.
    ui, out = terminal_ui()
    ui._live = MagicMock()
    ui.on_model_start()
    ui.on_text("➡️ Recommended answer: keep it short")
    ui.on_turn_end(AssistantTurn())
    shown = text_of(out)
    assert "️" not in shown and "➡ Recommended answer" in shown
    assert agent_ui.terminal_safe("ok ✔️") == "ok ✔"


def test_split_keeps_code_fences_whole():
    split = agent_ui.split_complete_blocks
    assert split("a\n\nb") == ("a\n\n", "b")
    assert split("a\n\n```py\nx = 1\n\ny = 2\n") == ("a\n\n", "```py\nx = 1\n\ny = 2\n")
    assert split("```\nx\n```\n\nmore") == ("```\nx\n```\n\n", "more")
    assert split("no break yet") == ("", "no break yet")


def test_working_line_counts_streamed_tokens():
    working = agent_ui._Working("Writing")
    working.chars = 4000
    console = Console(file=io.StringIO(), width=100, color_system=None)
    console.print(working)
    shown = console.file.getvalue()
    assert "↓ 1.0k tokens" in shown and "esc to interrupt" in shown


def shell_result(count):
    return json.dumps({"exit_code": 0, "stdout": "\n".join(f"line {i}" for i in range(count))})


def test_cut_output_can_be_expanded_after_the_request():
    ui, out = terminal_ui()
    ui.begin_request()
    ui.on_tool_start("run_shell_command", {"command": "pytest"})
    ui.on_tool_end("run_shell_command", shell_result(10), True)
    assert "… +6 lines (ctrl+o to expand)" in text_of(out)
    assert "line 9" not in text_of(out)
    ui.show_expanded()
    assert "● Bash(pytest)" in text_of(out) and "line 9" in text_of(out)
    ui.begin_request()  # a new request forgets the old output
    ui.show_expanded()
    assert "Nothing was cut short" in text_of(out)


def test_long_one_line_results_are_expandable_too():
    ui, out = terminal_ui()
    ui.on_tool_start("web_fetch", {"url": "https://x.dev"})
    ui.on_tool_end("web_fetch", "first line\nsecond line", True)
    assert "first line (ctrl+o to expand)" in text_of(out)
    assert ui.expandable == [("Fetch(https://x.dev)", "first line\nsecond line")]


def test_verbose_shows_output_in_full():
    ui, out = terminal_ui()
    ui.toggle_verbose()
    ui.on_tool_start("run_shell_command", {"command": "ls"})
    ui.on_tool_end("run_shell_command", shell_result(10), True)
    assert "line 9" in text_of(out) and "ctrl+o" not in text_of(out)


def test_bell_only_when_asked_for_and_after_a_long_request(monkeypatch):
    from joshu.core.config import get_config_manager

    # A plain terminal: no desktop notifications or progress indicator
    for name in ("WT_SESSION", "ConEmuPID", "TERM_PROGRAM", "KITTY_WINDOW_ID"):
        monkeypatch.delenv(name, raising=False)
    ui, out = terminal_ui()
    ui.begin_request()
    ui._request_started -= 60
    ui.notify()
    assert "\a" not in text_of(out)  # auto (default): no beep, only desktop notifications

    get_config_manager().set("notifications", "bell")
    ui, out = terminal_ui()
    ui.notify()
    assert "\a" not in text_of(out)  # no request started
    ui.begin_request()
    ui.notify()
    assert "\a" not in text_of(out)  # too quick
    ui._request_started -= 60
    ui.notify()
    assert "\a" in text_of(out)


def test_desktop_notification_where_supported(monkeypatch):
    monkeypatch.setenv("WT_SESSION", "1")
    monkeypatch.setenv("TERM_PROGRAM", "WezTerm")
    ui, out = terminal_ui()
    ui.begin_request()
    ui._request_started -= 60
    ui.notify("Done")
    assert text_of(out).count("\x1b]9;Done") == 1  # an OSC 9 notification


def test_working_line_names_the_task_in_progress():
    ui, _ = terminal_ui()
    todos = [
        {"description": "Write the parser", "status": "completed"},
        {"description": "Add tests", "status": "in_progress"},
    ]
    ui.on_tool_start("write_todos", {"todos": todos})
    ui.on_tool_end("write_todos", "{}", True)
    ui.on_model_start()
    assert ui._working is not None and ui._working.label == "Add tests"
    ui._stop_spinner()


def test_reasoning_folds_into_one_line_and_expands():
    ui, out = terminal_ui()
    ui._live = MagicMock()  # only what is printed for good
    ui.begin_request()
    ui.on_model_start()
    ui.on_reasoning("Check divisors.\n7 × 13 = 91.")
    assert "Check divisors" not in text_of(out)  # only in the live area while streaming
    ui.on_text("No, 91 = 7 × 13.")
    ui.on_turn_end(AssistantTurn())
    shown = text_of(out)
    assert "✻ Thought for 1s (ctrl+o to expand)" in shown
    assert shown.index("Thought for") < shown.index("● No, 91")
    ui.show_expanded()
    assert "7 × 13 = 91." in text_of(out)


def test_thinking_tail_shows_the_last_lines():
    ui, _ = terminal_ui()
    ui._thinking = "one\ntwo\nthree\nfour"
    tail = ui._thinking_tail(80)
    assert tail is not None and tail.plain == "  two\n  three\n  four"


def test_todo_progress_and_bottom_bar_activity():
    ui, _ = terminal_ui()
    todos = [
        {"description": "Parse", "status": "completed"},
        {"description": "Test", "status": "in_progress"},
        {"description": "Docs", "status": "pending"},
    ]
    ui.on_tool_start("write_todos", {"todos": todos})
    ui.on_tool_end("write_todos", "{}", True)
    assert ui.todo_progress == (1, 3, "Test")
    bar = "".join(text for _, text in bottom_toolbar("default", "m", activity="☐ 1/3 Test"))
    assert "? for shortcuts  ·  ☐ 1/3 Test" in bar


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


def test_new_file_shows_as_additions():
    ui, out = terminal_ui()
    ui.on_tool_start("write_file", {"path": "new.py", "content": "a = 1\nb = 2\n"})
    ui.on_tool_end("write_file", json.dumps({"success": True}), True)
    shown = text_of(out)
    assert "Wrote 2 lines to new.py" in shown
    assert "+ a = 1" in shown and "+ b = 2" in shown


def test_overwrite_shows_its_diff():
    ui, out = terminal_ui()
    ui.on_tool_start("write_file", {"path": "x.py", "content": "def f():\n    return 2\n"})
    ui.on_tool_end("write_file", json.dumps({"success": True, "diff": DIFF}), True)
    assert "Updated x.py with 1 addition and 1 removal" in text_of(out)


def test_long_diff_folds_and_ctrl_o_shows_all_of_it():
    ui, out = terminal_ui()
    content = "".join(f"line {i}\n" for i in range(40))
    ui.on_tool_start("write_file", {"path": "big.txt", "content": content})
    ui.on_tool_end("write_file", json.dumps({"success": True}), True)
    shown = text_of(out)
    assert "+ line 23" in shown and "+ line 24" not in shown
    assert "… +16 lines (ctrl+o to expand)" in shown
    ui.show_expanded()
    assert "+ line 39" in text_of(out)


def test_diff_lines_have_a_background():
    console = Console(file=io.StringIO(), width=60, color_system="truecolor", force_terminal=True)
    console.print(render_diff(DIFF, 10))
    added = next(line for line in console.file.getvalue().splitlines() if "return 2" in line)
    assert "48;2;" in added  # a background color


def test_edited_path_is_a_link():
    assert agent_ui._file_link("x.py").startswith("[link=file:")


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
