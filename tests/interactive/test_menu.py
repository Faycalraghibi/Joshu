"""Menus: number keys pick at once, Esc cancels, arrows and Enter work."""

import pytest

pytest.importorskip("prompt_toolkit")

from prompt_toolkit.application import create_app_session  # noqa: E402
from prompt_toolkit.input import create_pipe_input  # noqa: E402
from prompt_toolkit.output import DummyOutput  # noqa: E402

from joshu.ui.menu import menu  # noqa: E402

OPTIONS = [("yes", "Yes"), ("always", "Yes, always"), ("no", "No")]


def pick(keys, **kwargs):
    from unittest.mock import patch

    with create_pipe_input() as pipe, patch("joshu.ui.menu.can_show_menu", return_value=True):
        pipe.send_text(keys)
        with create_app_session(input=pipe, output=DummyOutput()):
            return menu("Allow?", OPTIONS, **kwargs)


def test_number_key_picks_without_enter():
    assert pick("2") == "always"
    assert pick("3") == "no"


def test_escape_returns_cancel():
    assert pick("\x1b", cancel="cancelled") == "cancelled"


def test_no_terminal_raises_menu_unavailable(monkeypatch):
    from joshu.ui.menu import MenuUnavailable

    monkeypatch.setattr("joshu.ui.menu.can_show_menu", lambda: False)
    with pytest.raises(MenuUnavailable):
        menu("Allow?", OPTIONS)


def test_arrows_and_enter():
    assert pick("\r") == "yes"
    assert pick("\x1b[B\x1b[B\r") == "no"
    assert pick("\r", default="always") == "always"


def pick_many(keys, **kwargs):
    from unittest.mock import patch

    from joshu.ui.menu import multi_menu

    with create_pipe_input() as pipe, patch("joshu.ui.menu.can_show_menu", return_value=True):
        pipe.send_text(keys)
        with create_app_session(input=pipe, output=DummyOutput()):
            return multi_menu("Which?", OPTIONS, **kwargs)


def test_multi_menu_number_keys_toggle_and_enter_confirms():
    assert pick_many("31\r") == ["yes", "no"]  # option order, not key order
    assert pick_many("11\r") == []


def test_multi_menu_space_selects_current():
    assert pick_many(" \x1b[B \r") == ["yes", "always"]


def test_multi_menu_escape_returns_cancel():
    assert pick_many("1\x1b", cancel="skipped") == "skipped"
