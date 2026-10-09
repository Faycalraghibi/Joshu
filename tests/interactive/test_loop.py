"""/loop: a prompt run again every interval, this session."""

import time
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from joshu.ui.interactive import loop as loop_module
from joshu.ui.interactive.loop import Loop, describe, parse_interval, parse_loop_args

pytest.importorskip("prompt_toolkit")


@pytest.fixture
def mode(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    from joshu.ui.interactive import InteractiveMode

    with patch("joshu.ui.interactive.interactive_mode.ContextProvider"):
        instance = InteractiveMode("test-model", sandbox=False, verbose=False)
    instance._show_message = MagicMock()
    return instance


@pytest.mark.parametrize(
    "text, seconds",
    [("30s", 30), ("5m", 300), ("2h", 7200), ("10", 600), ("5 m", 300), ("soon", None)],
)
def test_parse_interval(text, seconds):
    assert parse_interval(text) == seconds


def test_parse_loop_args():
    assert parse_loop_args("5m check the CI") == (300, "check the CI")
    assert parse_loop_args("check the CI") == (loop_module.DEFAULT_SECONDS, "check the CI")


def test_describe_and_schedule():
    job = Loop("x", 300, next_at=1000.0)
    assert describe(job, now=820.0) == "⟳ every 5m · next in 3m"
    assert job.due(now=1000.0) and not job.due(now=999.0)
    job.ran(now=1100.0)
    assert job.runs == 1 and job.next_at == 1400.0  # an interval after the run ended


def test_the_command(mode):
    handler = mode.command_handler
    handler.handle_slash_command("/loop 5m check the CI")
    assert mode.loop.prompt == "check the CI" and mode.loop.seconds == 300
    assert mode.loop.due()  # runs at once
    assert "⟳ every 5m" in mode.activity_text()
    handler.handle_slash_command("/loop 1s too fast")
    assert mode.loop.prompt == "check the CI"  # refused: below the minimum
    handler.handle_slash_command("/loop stop")
    assert mode.loop is None


def test_due_runs_go_before_the_prompt(mode):
    mode.loop = Loop("check the CI", 300)
    sent = []
    mode._handle_user_input = lambda text: sent.append(text) or True
    with patch("joshu.ui.interactive.interactive_mode.prompt", side_effect=EOFError):
        mode.start()
    assert sent == ["check the CI"]
    assert mode.loop.runs == 1 and mode.loop.next_at > time.time() + 290


def test_a_due_run_interrupts_the_waiting_prompt(mode):
    from joshu.ui.interactive.interactive_mode import LOOP_DUE

    results = []
    app = SimpleNamespace(
        is_running=True,
        current_buffer=SimpleNamespace(text="half typed"),
        loop=SimpleNamespace(call_soon_threadsafe=lambda fn: fn()),
        exit=lambda result: results.append(result),
    )
    mode.loop = Loop("check", 300, next_at=time.time() + 0.1)
    with patch("prompt_toolkit.application.current.get_app", return_value=app):
        mode._arm_loop_timer()
    deadline = time.time() + 5
    while not results and time.time() < deadline:
        time.sleep(0.02)
    assert results == [LOOP_DUE] and mode.type_ahead == "half typed"
    mode._cancel_loop_timer()


def test_text_typed_before_a_run_carries_on():
    from joshu.ui.key_listener import KeyListener

    listener = KeyListener(initial="half typed")
    for key in " more":
        listener._add(key)
    assert listener.typed == "half typed more"
