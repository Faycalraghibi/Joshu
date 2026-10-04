"""Esc to interrupt, type-ahead, /rewind, /compact, /init and slash completion."""

import sys
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "core"))

from test_agent_loop import FakeClient, call, make_agent, text  # noqa: E402

from joshu.core.compaction import SUMMARY_PREFIX  # noqa: E402
from joshu.core.permissions import PermissionMode  # noqa: E402
from joshu.tools import filesystem_tools  # noqa: E402
from joshu.ui import key_listener  # noqa: E402
from joshu.ui.key_listener import ESC, KeyListener, paused  # noqa: E402


@pytest.fixture
def workspace(tmp_path):
    filesystem_tools.set_workspace_root(tmp_path)
    yield tmp_path
    filesystem_tools._workspace_root = None


def edit(path, old, new, call_id="c1"):
    return call("replace", call_id=call_id, path=path, old_string=old, new_string=new)


def two_edits_agent(workspace):
    (workspace / "a.txt").write_text("one", encoding="utf-8")
    client = FakeClient(
        [
            edit("a.txt", "one", "two"),
            text("first done"),
            edit("a.txt", "two", "three", call_id="c2"),
            text("second done"),
        ]
    )
    agent = make_agent(client, mode=PermissionMode.ACCEPT_EDITS)
    agent.run("make it two")
    agent.run("make it three")
    return agent


# ------------------------------------------------------------------ rewind


def test_rewind_drops_last_request_and_restores_its_files(workspace):
    agent = two_edits_agent(workspace)
    assert (workspace / "a.txt").read_text(encoding="utf-8") == "three"

    rewind = agent.rewind()

    assert rewind.prompts == ["make it three"]
    assert [p.name for p in rewind.files] == ["a.txt"]
    assert (workspace / "a.txt").read_text(encoding="utf-8") == "two"
    assert agent.requests() == ["make it two"]
    assert agent.messages[-1]["content"] == "first done"


def test_rewind_several_requests(workspace):
    agent = two_edits_agent(workspace)
    rewind = agent.rewind(5)  # more than there are: rewinds all
    assert rewind.prompts == ["make it two", "make it three"]
    assert (workspace / "a.txt").read_text(encoding="utf-8") == "one"
    assert len(agent.messages) == 1  # only the system prompt
    assert agent.rewind() is None


def test_new_requests_after_rewind_are_tracked(workspace):
    agent = two_edits_agent(workspace)
    agent.rewind()
    agent.client.turns = [edit("a.txt", "two", "four", call_id="c3"), text("ok")]
    agent.run("make it four")
    assert (workspace / "a.txt").read_text(encoding="utf-8") == "four"
    agent.rewind()
    assert (workspace / "a.txt").read_text(encoding="utf-8") == "two"


def test_rewind_stops_at_compaction_summary(workspace):
    agent = make_agent(FakeClient([]))
    agent.messages += [
        {"role": "user", "content": SUMMARY_PREFIX + "earlier work"},
        {"role": "user", "content": "latest"},
        {"role": "assistant", "content": "answer"},
    ]
    assert agent.rewind(3).prompts == ["latest"]
    assert agent.messages[-1]["content"].startswith(SUMMARY_PREFIX)


# ----------------------------------------------------------------- compact


def test_compact_with_focus(workspace):
    client = FakeClient(
        [text("a1"), text("a2"), text("the summary")]  # two requests, then the summary
    )
    agent = make_agent(client)
    agent.run("first")
    agent.run("second")

    assert agent.compact("the API design") is not None

    summary_request = client.requests[-1]
    assert "focus on: the API design" in summary_request[0]["content"]
    assert agent.messages[1]["content"] == SUMMARY_PREFIX + "the summary"
    assert agent.requests() == ["second"]


def test_compact_with_nothing_to_compact(workspace):
    agent = make_agent(FakeClient([]))
    assert agent.compact() is None


# ---------------------------------------------------------------- listener


def test_listener_collects_type_ahead():
    listener = KeyListener()
    for key in "fix tha\x08e tests\r":
        listener._add(key)
    assert listener.typed == "fix the tests"


def test_listener_is_inert_without_a_terminal():
    with patch.object(key_listener, "_is_terminal", return_value=False):
        with KeyListener() as listener:
            assert listener._thread is None
            with paused():
                pass


def test_esc_interrupts_the_main_thread():
    keys = iter([None, "h", "i", ESC])

    def fake_read(timeout):
        time.sleep(0.01)
        return next(keys, None)

    with (
        patch.object(key_listener, "_is_terminal", return_value=True),
        patch.object(KeyListener, "_enter_raw"),
        patch.object(KeyListener, "_leave_raw"),
        patch.object(key_listener, "_read_key", side_effect=fake_read),
    ):
        listener = KeyListener()
        with pytest.raises(KeyboardInterrupt):
            with listener:
                for _ in range(500):
                    time.sleep(0.01)
    assert listener.interrupted
    assert listener.typed == "hi"


def test_action_keys_run_instead_of_being_typed():
    keys = iter([None, "a", key_listener.CTRL_O, "b", ESC])
    toggled = []

    def fake_read(timeout):
        time.sleep(0.01)
        return next(keys, None)

    with (
        patch.object(key_listener, "_is_terminal", return_value=True),
        patch.object(KeyListener, "_enter_raw"),
        patch.object(KeyListener, "_leave_raw"),
        patch.object(key_listener, "_read_key", side_effect=fake_read),
    ):
        listener = KeyListener({key_listener.CTRL_O: lambda: toggled.append(1)})
        with pytest.raises(KeyboardInterrupt):
            with listener:
                for _ in range(500):
                    time.sleep(0.01)
    assert toggled == [1] and listener.typed == "ab"


def test_paused_listener_reads_no_keys():
    reads = []

    def fake_read(timeout):
        reads.append(1)
        time.sleep(0.01)
        return None

    with (
        patch.object(key_listener, "_is_terminal", return_value=True),
        patch.object(KeyListener, "_enter_raw"),
        patch.object(KeyListener, "_leave_raw"),
        patch.object(key_listener, "_read_key", side_effect=fake_read),
    ):
        with KeyListener():
            time.sleep(0.05)
            with paused():
                count = len(reads)
                time.sleep(0.1)
                assert len(reads) <= count + 1  # at most the poll in progress


# ---------------------------------------------------------------- commands


def handler_with(agent):
    from joshu.ui.interactive.commands import CommandHandler

    mode = MagicMock()
    mode.agent = agent
    mode.type_ahead = ""
    return mode, CommandHandler(mode)


def test_rewind_command_restores_and_offers_prompt(workspace):
    agent = two_edits_agent(workspace)
    mode, handler = handler_with(agent)

    assert handler.handle_slash_command("/rewind")
    shown = mode._show_message.call_args[0][0]
    assert "make it three" in shown and "a.txt" in shown
    assert mode.type_ahead == "make it three"


def test_rewind_command_usage_and_empty(workspace):
    mode, handler = handler_with(make_agent(FakeClient([])))
    handler.handle_slash_command("/rewind x")
    assert "Usage" in mode._show_message.call_args[0][0]
    handler.handle_slash_command("/rewind")
    assert mode._show_message.call_args[0][0] == "Nothing to rewind."


def test_compact_command(workspace):
    agent = MagicMock()
    agent.compact.return_value = (5000, 800)
    mode, handler = handler_with(agent)
    handler.handle_slash_command("/compact keep the test plan")
    agent.compact.assert_called_once_with("keep the test plan")
    assert "5,000 -> ~800" in mode._show_message.call_args[0][0]


def test_init_command_runs_agent_with_agents_md_prompt():
    mode, handler = handler_with(None)
    mode._ensure_agent.return_value = True
    handler.handle_slash_command("/init we use uv")
    prompt = mode._run_agent.call_args[0][0]
    assert "AGENTS.md" in prompt and "The user adds: we use uv" in prompt


# --------------------------------------------------------------- completer


def test_slash_command_completion():
    from prompt_toolkit.document import Document

    from joshu.ui.interactive.completers import get_command_completer

    completer = get_command_completer(["/deploy"])
    names = lambda text: [c.text for c in completer.get_completions(Document(text), None)]  # noqa: E731

    assert names("/re") == ["/release-notes", "/reset", "/resume", "/review", "/rewind"]
    assert names("/dep") == ["/deploy"]
    assert names("hello /re") == []
    assert names("/rewind 2") == []
