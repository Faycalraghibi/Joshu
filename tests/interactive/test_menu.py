"""Menus: number keys pick at once, Esc cancels, arrows and Enter work."""

import pytest

pytest.importorskip("prompt_toolkit")

from prompt_toolkit.application import create_app_session  # noqa: E402
from prompt_toolkit.input import create_pipe_input  # noqa: E402
from prompt_toolkit.output import DummyOutput  # noqa: E402

from joshu.ui.menu import menu  # noqa: E402

OPTIONS = [("yes", "Yes"), ("always", "Yes, always"), ("no", "No")]


def pick(keys, **kwargs):
    with create_pipe_input() as pipe:
        pipe.send_text(keys)
        with create_app_session(input=pipe, output=DummyOutput()):
            return menu("Allow?", OPTIONS, **kwargs)


def test_number_key_picks_without_enter():
    assert pick("2") == "always"
    assert pick("3") == "no"


def test_escape_returns_cancel():
    assert pick("\x1b", cancel="cancelled") == "cancelled"


def test_arrows_and_enter():
    assert pick("\r") == "yes"
    assert pick("\x1b[B\x1b[B\r") == "no"
    assert pick("\r", default="always") == "always"
