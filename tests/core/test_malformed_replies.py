"""Broken final replies go back to the model instead of ending the request."""

import json

import pytest
from test_agent_loop import FakeClient, call, make_agent, text

from joshu.core.agent import (
    AFTER_FAILURE_NOTE,
    MAX_MALFORMED_RETRIES,
    TOOL_AS_TEXT_NOTE,
    malformed_reply,
)


@pytest.fixture(autouse=True)
def retries_on():
    from joshu.core.config import get_config_manager

    get_config_manager().set("retry_broken_replies", True)


@pytest.mark.parametrize(
    "reply, failed, note",
    [
        ("Nowells </function> </tool_call>", False, TOOL_AS_TEXT_NOTE),
        ('<tool_call>{"name": "read_file", "arguments": {}}</tool_call>', False, TOOL_AS_TEXT_NOTE),
        ('{"name": "replace", "arguments": {"path": "a.py"}}', False, TOOL_AS_TEXT_NOTE),
        ("ichten United. and-------------", True, AFTER_FAILURE_NOTE),
        ("", True, AFTER_FAILURE_NOTE),
        ("Done: the cache evicts the least recently used entry and expires old ones.", False, None),
        ("ichten United.", False, None),  # short, but nothing failed
        (
            "The search failed because the pattern was empty; there is no such function in "
            "the project, so nothing needs to change.",
            True,
            None,
        ),
    ],
)
def test_malformed_reply(reply, failed, note):
    assert malformed_reply(reply, failed) == note


def test_tool_call_written_as_text_is_sent_back(tmp_path):
    client = FakeClient([text("Nowells </function> </tool_call>"), text("Implemented it.")])
    response = make_agent(client, cwd=tmp_path).run("implement the cache")
    assert response.text == "Implemented it."
    assert client.requests[1][-1] == {"role": "user", "content": TOOL_AS_TEXT_NOTE}


def test_gibberish_after_a_failed_call_is_sent_back(tmp_path):
    client = FakeClient(
        [
            call("search_file_content"),  # missing its pattern: fails
            text("ichten United."),
            text("I searched with the wrong arguments; here is the answer."),
        ]
    )
    response = make_agent(client, cwd=tmp_path).run("migrate the client")
    assert response.text.startswith("I searched")
    assert client.requests[2][-1]["content"] == AFTER_FAILURE_NOTE


def test_at_most_twice_per_request(tmp_path):
    turns = [text("<tool_call>x</tool_call>")] * (MAX_MALFORMED_RETRIES + 1)
    client = FakeClient(turns)
    response = make_agent(client, cwd=tmp_path).run("go")
    assert response.text == "<tool_call>x</tool_call>"
    assert len(client.requests) == MAX_MALFORMED_RETRIES + 1


def test_the_setting_turns_it_off(tmp_path):
    from joshu.core.config import get_config_manager

    get_config_manager().set("retry_broken_replies", False)
    client = FakeClient([text("<tool_call>x</tool_call>")])
    assert make_agent(client, cwd=tmp_path).run("go").text == "<tool_call>x</tool_call>"


def test_a_failure_reported_as_json_counts(tmp_path):
    from joshu.core.agent import _tool_failed

    assert _tool_failed(json.dumps({"success": False, "error": "x"}))
    assert _tool_failed("Error: invalid arguments")
    assert not _tool_failed(json.dumps({"success": True}))
    assert not _tool_failed("plain output")
