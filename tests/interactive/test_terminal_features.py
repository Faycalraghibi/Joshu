"""Desktop notifications and the progress indicator, per terminal."""

import io

import pytest
from rich.console import Console

from joshu.ui import terminal_features as tf
from joshu.ui.agent_ui import ConsoleAgentUI


@pytest.fixture(autouse=True)
def plain_terminal(monkeypatch):
    """Start from a terminal with no extra features (tests run inside real ones)."""
    for name in ("WT_SESSION", "ConEmuPID", "TERM_PROGRAM", "KITTY_WINDOW_ID"):
        monkeypatch.delenv(name, raising=False)


def test_notification_sequence_per_terminal():
    assert tf.notification_sequence("done", {"TERM_PROGRAM": "iTerm.app"}) == "\x1b]9;done\x07"
    assert tf.notification_sequence("done", {"KITTY_WINDOW_ID": "1"}) == "\x1b]99;;done\x1b\\"
    assert tf.notification_sequence("done", {}) == ""
    # Control characters can't end the sequence early
    assert tf.notification_sequence("a\x07b", {"TERM_PROGRAM": "WezTerm"}) == "\x1b]9;ab\x07"


def test_progress_support():
    assert tf.supports_progress({"WT_SESSION": "x"})
    assert tf.supports_progress({"TERM_PROGRAM": "ghostty"})
    assert not tf.supports_progress({})


def make_ui():
    out = io.StringIO()
    return ConsoleAgentUI(Console(file=out, force_terminal=True, width=80)), out


def test_long_request_notifies_on_desktop_where_supported(monkeypatch):
    monkeypatch.setenv("TERM_PROGRAM", "WezTerm")
    ui, out = make_ui()
    ui.begin_request()
    ui._request_started -= 60
    ui.notify("Joshu needs your approval")
    assert "\x1b]9;Joshu needs your approval\x07" in out.getvalue()
    rest = out.getvalue().replace("\x1b]9;Joshu needs your approval\x07", "")
    assert "\a" not in rest.replace(tf.PROGRESS_BUSY, "")  # no bell as well


def test_progress_is_set_and_cleared(monkeypatch):
    monkeypatch.setenv("WT_SESSION", "1")
    ui, out = make_ui()
    ui.begin_request()
    assert tf.PROGRESS_BUSY in out.getvalue()
    ui.end_request()
    assert out.getvalue().endswith(tf.PROGRESS_CLEAR)


def test_no_progress_in_other_terminals():
    ui, out = make_ui()
    ui.begin_request()
    ui.end_request()
    assert "\x1b]9;4" not in out.getvalue()
