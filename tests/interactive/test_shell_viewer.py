"""The background shells viewer, and how it is opened from the prompt."""

import sys
import time
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import patch

import pytest

pytest.importorskip("prompt_toolkit")

from prompt_toolkit import PromptSession  # noqa: E402
from prompt_toolkit.application import create_app_session  # noqa: E402
from prompt_toolkit.input import create_pipe_input  # noqa: E402
from prompt_toolkit.output import DummyOutput  # noqa: E402

from joshu.tools import shell_tool  # noqa: E402
from joshu.ui.interactive.keybindings import create_key_bindings  # noqa: E402
from joshu.ui.interactive.prompt import bottom_toolbar  # noqa: E402
from joshu.ui.shell_viewer import ShellViewer, elapsed_since, run_viewer  # noqa: E402

UP, DOWN, ESC = "\x1b[A", "\x1b[B", "\x1b"


def fake(process_id, command, code=None, log=None):
    return SimpleNamespace(
        process_id=process_id,
        command=command,
        started_at=(datetime.now() - timedelta(seconds=75)).isoformat(),
        process=SimpleNamespace(poll=lambda: code),
        log_path=log,
        read_offset=0,
    )


def text(fragments):
    return "".join(part for _style, part in fragments)


def test_elapsed_since():
    now = datetime(2026, 1, 1, 12, 0, 0)
    assert elapsed_since("2026-01-01T11:59:56", now) == "4s"
    assert elapsed_since("2026-01-01T11:57:55", now) == "2m 05s"
    assert elapsed_since("2026-01-01T10:57:00", now) == "1h 03m"
    assert elapsed_since("garbage", now) == ""


def test_list_then_output_then_back(tmp_path):
    log = tmp_path / "out.log"
    log.write_text("".join(f"line {i}\n" for i in range(100)), encoding="utf-8")
    processes = [fake("bash_1", "npm run dev", log=log), fake("bash_2", "pytest", code=1)]
    viewer = ShellViewer(lambda: processes)

    shown = text(viewer.render(100, 30))
    assert "❯ bash_1" in shown and "● running 1m 15s" in shown and "○ exited 1" in shown
    viewer.move(1)
    assert "❯ bash_2" in text(viewer.render(100, 30))
    viewer.move(1)  # wraps around
    viewer.enter()

    shown = text(viewer.render(100, 30))
    assert "npm run dev" in shown and "line 99" in shown
    assert "line 70" not in shown  # only the end that fits
    assert processes[0].read_offset == 0  # the agent still gets all of it from bash_output
    assert viewer.back() is False
    assert "Background shells" in text(viewer.render(100, 30))
    assert viewer.back() is True


def test_kill_from_the_viewer():
    started = shell_tool.start_background_process(
        f'"{sys.executable}" -c "import time; print(1, flush=True); time.sleep(30)"'
    )
    viewer = ShellViewer()
    try:
        viewer.index = [p.process_id for p in viewer.processes()].index(started["process_id"])
        viewer.enter()
        for _ in range(50):
            if "1" in text(viewer.render(80, 20)).split("─")[-2]:
                break
            time.sleep(0.1)
        viewer.kill()
    finally:
        shell_tool.stop_background_process(started["process_id"])
    assert viewer.opened is None and viewer.message
    assert all(
        p.process_id != started["process_id"] for p in shell_tool.list_background_processes()
    )


def test_run_viewer_reads_keys():
    processes = [fake("bash_1", "npm run dev"), fake("bash_2", "pytest", code=0)]
    viewer = ShellViewer(lambda: processes)
    with create_pipe_input() as pipe:
        pipe.send_text(DOWN + "\r" + ESC + ESC)
        with create_app_session(input=pipe, output=DummyOutput()):
            run_viewer(viewer)
    assert viewer.index == 1 and viewer.opened is None


def prompt_with(keys, processes):
    mode = SimpleNamespace(vim_enabled=False, notice="", cycle_mode=lambda: "")
    with (
        create_pipe_input() as pipe,
        patch.object(shell_tool, "list_background_processes", return_value=processes),
    ):
        pipe.send_text(keys)
        session = PromptSession(
            input=pipe, output=DummyOutput(), key_bindings=create_key_bindings(mode)
        )
        return session.prompt("> ")


def test_down_on_empty_prompt_opens_the_viewer():
    assert prompt_with(DOWN, [fake("bash_1", "npm run dev")]) == "/bashes"


def test_down_does_nothing_special_otherwise():
    assert prompt_with(DOWN + "ok\r", []) == "ok"
    assert prompt_with("draft" + DOWN + "\r", [fake("bash_1", "x")]) == "draft"


def test_bottom_bar_says_how_to_view():
    with patch.object(shell_tool, "running_background_count", return_value=2):
        from joshu.ui.interactive.interactive_mode import InteractiveMode

        activity = InteractiveMode.activity_text(SimpleNamespace(agent_ui=None))
    assert activity == "2 shells · ↓ to view"
    shown = "".join(part for _style, part in bottom_toolbar("default", activity=activity))
    assert "↓ to view" in shown
