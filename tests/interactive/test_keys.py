"""Input keys, sent as raw terminal bytes to a real prompt_toolkit prompt."""

import threading
from types import SimpleNamespace

import pytest

pytest.importorskip("prompt_toolkit")

from prompt_toolkit import PromptSession  # noqa: E402
from prompt_toolkit.history import InMemoryHistory  # noqa: E402
from prompt_toolkit.input import create_pipe_input  # noqa: E402
from prompt_toolkit.output import DummyOutput  # noqa: E402

from joshu.ui.interactive.keybindings import create_key_bindings  # noqa: E402

ESC = "\x1b"


def ask(keys: str, vim: bool = False, history=(), delay: float = 0.0):
    """Type `keys` into a prompt with Joshu's bindings and return what it submits."""
    mode = SimpleNamespace(vim_enabled=vim, notice="", cycle_mode=lambda: "plan")
    stored = InMemoryHistory()
    for entry in history:
        stored.append_string(entry)
    with create_pipe_input() as pipe:
        if delay:
            # The prompt loads its history in the background when it starts
            threading.Timer(delay, pipe.send_text, [keys]).start()
        else:
            pipe.send_text(keys)
        session = PromptSession(
            input=pipe,
            output=DummyOutput(),
            key_bindings=create_key_bindings(mode),
            history=stored,
            vi_mode=vim,
        )
        return session.prompt("> "), mode


def test_enter_submits_and_backslash_continues():
    assert ask("one\\\rtwo\r")[0] == "one\ntwo"


def test_ctrl_d_deletes_a_character_when_there_is_text():
    # Home, Ctrl+D: deletes "x" instead of exiting
    assert ask("xab\x01\x04\r")[0] == "ab"


def test_ctrl_d_on_empty_prompt_exits():
    with pytest.raises(EOFError):
        ask("\x04")


def test_ctrl_c_clears_the_input_first():
    text, mode = ask("draft\x03kept\r")
    assert text == "kept"


def test_escape_clears_the_input():
    assert ask("draft" + ESC + "kept\r")[0] == "kept"


def test_shift_tab_cycles_the_mode():
    calls = []
    mode = SimpleNamespace(vim_enabled=False, notice="x", cycle_mode=lambda: calls.append(1))
    with create_pipe_input() as pipe:
        pipe.send_text(ESC + "[Z" + "go\r")
        session = PromptSession(
            input=pipe, output=DummyOutput(), key_bindings=create_key_bindings(mode)
        )
        assert session.prompt("> ") == "go"
    assert calls == [1] and mode.notice == ""


def test_ctrl_r_searches_history():
    text, _ = ask("\x12alp\r\r", history=["alpha one", "beta two"], delay=0.3)
    assert text == "alpha one"


def test_vim_mode_uses_normal_mode_motions():
    # Esc to NORMAL, 0 to line start, x deletes a char, A appends at the end
    assert ask("hello" + ESC + "0xA!\r", vim=True)[0] == "ello!"
