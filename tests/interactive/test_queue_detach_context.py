"""Queued messages, Ctrl+B to background a command, the context indicator, fast startup."""

import subprocess
import sys
import threading
import time
from unittest.mock import MagicMock, patch

import pytest

from joshu.tools import shell_tool

pytest.importorskip("prompt_toolkit")


@pytest.fixture
def mode(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    from joshu.ui.interactive import InteractiveMode

    with patch("joshu.ui.interactive.interactive_mode.ContextProvider"):
        instance = InteractiveMode("test-model", sandbox=False, verbose=False)
    instance._show_message = MagicMock()
    return instance


# ---------------------------------------------------------------- queue


def test_enter_while_running_queues_and_btw_still_answers(mode):
    assert mode._submit_while_running("then add tests") is True
    assert mode.queued == ["then add tests"]
    mode.agent = MagicMock()
    mode.agent.side_question.return_value = "x"
    mode.agent_ui = MagicMock()
    assert mode._submit_while_running("/btw what is it?") is True
    assert mode.queued == ["then add tests"]  # a side question isn't queued


def test_queued_messages_are_sent_in_order(mode):
    mode.queued = ["first", "second"]
    sent = []

    def handle(text):
        sent.append(text)
        return len(sent) < 2  # leave after the second

    mode._handle_user_input = handle
    with patch("joshu.ui.interactive.interactive_mode.prompt") as prompt:
        mode.start()
    assert sent == ["first", "second"] and not prompt.called
    assert "> first" in [c.args[0] for c in mode._show_message.call_args_list]


# ---------------------------------------------------------------- ctrl+b

TICKER = (
    "import time, sys\n"
    "print('started', flush=True)\n"
    "for i in range(100):\n"
    "    print(f'tick {i}', flush=True)\n"
    "    time.sleep(0.1)\n"
)


def test_ctrl_b_moves_a_running_command_to_the_background(tmp_path):
    script = tmp_path / "ticker.py"
    script.write_text(TICKER, encoding="utf-8")
    shell_tool.set_detachable(True)
    try:

        def press_ctrl_b():
            deadline = time.time() + 10
            while time.time() < deadline and not shell_tool.foreground_running():
                time.sleep(0.05)
            time.sleep(0.5)
            assert shell_tool.request_detach()

        presser = threading.Thread(target=press_ctrl_b)
        presser.start()
        result = shell_tool.run_shell_command_tool(f'"{sys.executable}" "{script}"', timeout=60)
        presser.join()
        assert result["backgrounded"] and "started" in result["stdout"]
        process_id = result["process_id"]
        time.sleep(0.5)
        later = shell_tool.bash_output_tool(process_id)
        assert later["status"] == "running" and "tick" in later["output"]
        assert "started" not in later["output"]  # only what came after
    finally:
        shell_tool.set_detachable(False)
        shell_tool.stop_background_process(result["process_id"])
    assert not shell_tool.request_detach()  # nothing running now


def test_detachable_run_finishes_like_a_normal_one(tmp_path):
    shell_tool.set_detachable(True)
    try:
        command = f"\"{sys.executable}\" -c \"import sys; print('out'); print('err', file=sys.stderr); sys.exit(3)\""
        result = shell_tool.run_shell_command_tool(command)
    finally:
        shell_tool.set_detachable(False)
    assert result["exit_code"] == 3 and not result["success"]
    assert result["stdout"].strip() == "out" and result["stderr"].strip() == "err"
    timed = shell_tool.run_detachable(
        f'"{sys.executable}" -c "import time; time.sleep(30)"', timeout=1
    )
    assert "timed out" in timed["error"]


# --------------------------------------------------------------- context


def test_context_indicator(mode):
    mode.context_level = 30
    assert "context" not in mode.activity_text()
    mode.context_level = 72
    assert "context 72%" in mode.activity_text() and "/compact" not in mode.activity_text()
    mode.context_level = 85
    assert "context 85% · /compact" in mode.activity_text()
    mode.queued = ["x"]
    assert "1 queued" in mode.activity_text()

    agent = MagicMock(context_window=1000)
    agent.messages = [{"role": "user", "content": "x" * 2400}]
    mode.agent = agent
    mode._update_context_level()
    assert 50 <= mode.context_level <= 70

    agent.background_running.return_value = ["a", "b"]
    assert "2 agents working" in mode.activity_text()


# ---------------------------------------------------------------- startup


def test_cli_doesnt_load_the_heavy_parts_at_startup():
    code = (
        "import sys, joshu.ui.cli; "
        "print([m for m in ('prompt_toolkit', 'joshu.mcp.discovery', 'httpx', "
        "'joshu.ui.interactive.interactive_mode') if m in sys.modules])"
    )
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert out.stdout.strip() == "[]", out.stderr


def test_mcp_starts_in_the_background_and_the_agent_waits(monkeypatch):
    from joshu.mcp import startup

    startup.reset()
    calls = []

    def slow_load(report=None):
        time.sleep(0.3)
        calls.append("loaded")
        return 0

    monkeypatch.setattr(startup, "_loaded", False)
    thread = threading.Thread(target=slow_load)
    monkeypatch.setattr(startup, "_background", thread)
    thread.start()
    assert startup.mcp_loading()
    assert startup.load_mcp_tools() == 0  # waits for the background start
    assert calls == ["loaded"] and not startup.mcp_loading()
    startup.reset()


def test_background_work_starts_once_after_the_prompt(mode, monkeypatch):
    calls = []
    monkeypatch.setattr(
        "joshu.mcp.startup.load_mcp_tools_in_background", lambda: calls.append("mcp")
    )
    monkeypatch.setattr(
        "joshu.ui.interactive.interactive_mode.warm_up_in_background",
        lambda: calls.append("warm"),
    )
    mode._start_background_work()
    mode._start_background_work()  # every prompt calls it; only the first starts work
    assert calls == ["mcp", "warm"]


def test_warm_up_imports_in_the_background(monkeypatch):
    from joshu.ui.interactive import interactive_mode

    monkeypatch.setattr(interactive_mode, "WARM_UP_MODULES", ("json", "no_such_module_xyz"))
    sys.modules.pop("json", None)
    interactive_mode.warm_up_in_background()
    deadline = time.time() + 5
    while "json" not in sys.modules and time.time() < deadline:
        time.sleep(0.01)
    assert "json" in sys.modules  # and the missing one didn't raise


def test_interactive_mode_doesnt_load_mcp_or_markdown_up_front():
    code = (
        "import sys, joshu.ui.interactive.interactive_mode; "
        "print([m for m in ('joshu.mcp.loop', 'joshu.mcp.discovery', 'rich.markdown', 'openai') "
        "if m in sys.modules])"
    )
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert out.stdout.strip() == "[]", out.stderr


def test_an_approved_plan_leaves_plan_mode(mode):
    from joshu.core.permissions import PermissionMode

    mode.interaction_mode = "plan"
    mode.agent = MagicMock()
    mode.agent.permissions.mode = PermissionMode.PLAN
    mode._follow_plan_approval()
    assert mode.current_mode() == "plan"  # not approved: still planning
    mode.agent.permissions.mode = PermissionMode.ACCEPT_EDITS
    mode._follow_plan_approval()
    assert mode.current_mode() == "accept_edits" and mode.interaction_mode == "agent"
