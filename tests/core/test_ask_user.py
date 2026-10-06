"""The ask_user tool: validating questions, formatting answers, wiring."""

import json

import pytest

from joshu.core.ask import AskError, Question, format_answers, parse_questions
from tests.core.test_agent_loop import (
    FakeClient,
    RecordingEvents,
    call,
    make_agent,
    text,
    tool_messages,
)

COLOR = {
    "question": "Which color?",
    "header": "Color",
    "options": [{"label": "Red", "description": "warm"}, {"label": "Blue"}],
}


def test_parse_questions_accepts_valid_input():
    (q,) = parse_questions([COLOR])
    assert q == Question("Which color?", [("Red", "warm"), ("Blue", "")], False, "Color")
    assert parse_questions(json.dumps([COLOR]))[0].question == "Which color?"
    assert parse_questions([{"question": "x?", "options": ["a", "b"]}])[0].options == [
        ("a", ""),
        ("b", ""),
    ]


@pytest.mark.parametrize(
    "raw",
    [
        [],
        "not json",
        [COLOR] * 5,
        [{"options": ["a", "b"]}],
        [{"question": "x?", "options": ["only one"]}],
        [{"question": "x?", "options": [str(i) for i in range(7)]}],
        [{"question": "x?", "options": [{"description": "no label"}, "b"]}],
    ],
)
def test_parse_questions_rejects_malformed(raw):
    with pytest.raises(AskError):
        parse_questions(raw)


def test_format_answers():
    single = Question("One?", [("a", ""), ("b", "")])
    multi = Question("Many?", [("a", ""), ("b", "")], multi_select=True)
    typed = Question("Typed?", [("a", ""), ("b", "")])
    skipped = Question("Skip?", [("a", ""), ("b", "")])
    out = json.loads(
        format_answers([single, multi, typed, skipped], [["b"], ["a", "b"], "my own", None])
    )
    assert out["answered"] is True
    answers = [a["answer"] for a in out["answers"]]
    assert answers == ["b", ["a", "b"], "my own", None]
    assert "skipped" in out["answers"][3]["note"]
    assert json.loads(format_answers([single], None))["answered"] is False


class AskingEvents(RecordingEvents):
    can_ask_user = True

    def __init__(self, answers):
        super().__init__()
        self.answers = answers
        self.asked = []

    def ask_user(self, questions):
        self.asked.append(questions)
        return self.answers


def offered(client):
    return {t["function"]["name"] for t in client.tools_offered[0] or []}


def test_tool_only_offered_when_someone_can_answer(tmp_path):
    client = FakeClient([text("hi")])
    make_agent(client, cwd=tmp_path).run("hello")
    assert "ask_user" not in offered(client)

    client = FakeClient([text("hi")])
    make_agent(client, cwd=tmp_path, events=AskingEvents(None)).run("hello")
    assert "ask_user" in offered(client)


def test_answers_reach_the_model(tmp_path):
    events = AskingEvents([["Blue"]])
    client = FakeClient([call("ask_user", questions=[COLOR]), text("Blue it is.")])
    response = make_agent(client, cwd=tmp_path, events=events).run("paint it")
    assert response.text == "Blue it is."
    assert events.asked[0][0].question == "Which color?"
    result = json.loads(tool_messages(client.requests[1])[0]["content"])
    assert result["answers"][0]["answer"] == "Blue"


def test_malformed_questions_return_an_error_without_asking(tmp_path):
    events = AskingEvents([["Blue"]])
    client = FakeClient(
        [call("ask_user", questions=[{"question": "x?", "options": ["a"]}]), text("ok")]
    )
    make_agent(client, cwd=tmp_path, events=events).run("go")
    assert events.asked == []
    assert "Error" in tool_messages(client.requests[1])[0]["content"]


# --------------------------------------------------------------- terminal UI


def answer_typed(monkeypatch, question, replies, picked=None):
    """Run the terminal's _ask_one with `replies` typed at input()."""
    from joshu.ui import agent_ui
    from joshu.ui.menu import MenuUnavailable

    def no_menu(*args, **kwargs):
        if picked is not None:
            return picked
        raise MenuUnavailable("test")

    monkeypatch.setattr("joshu.ui.menu.menu", no_menu)
    monkeypatch.setattr("joshu.ui.menu.multi_menu", no_menu)
    feed = iter(replies)
    monkeypatch.setattr("builtins.input", lambda prompt="": next(feed))
    return agent_ui._ask_one(question)


def test_typed_fallback(monkeypatch):
    single = Question("One?", [("a", ""), ("b", "x")])
    multi = Question("Many?", [("a", ""), ("b", "")], multi_select=True)
    assert answer_typed(monkeypatch, single, ["9", "2"]) == ["b"]  # retries bad input
    assert answer_typed(monkeypatch, multi, ["2, 1"]) == ["b", "a"]
    assert answer_typed(monkeypatch, single, [""]) is None
    assert answer_typed(monkeypatch, single, ["3", "my own idea"]) == "my own idea"


def test_other_from_the_menu_asks_for_text(monkeypatch):
    from joshu.ui.agent_ui import OTHER

    multi = Question("Many?", [("a", ""), ("b", "")], multi_select=True)
    assert answer_typed(monkeypatch, multi, ["c"], picked=["a", OTHER]) == "a, c"
    assert answer_typed(monkeypatch, multi, [""], picked=[OTHER]) is None


# ----------------------------------------------------------------------- SDK


def test_sdk_ask_user_callback(tmp_path):
    from joshu.sdk import Session

    seen = []

    def ask(questions):
        seen.append(questions[0].question)
        return [["Red"]]

    client = FakeClient([call("ask_user", questions=[COLOR]), text("Red.")])
    session = Session(client=client, cwd=tmp_path, ask_user=ask)
    assert session.send("paint").text == "Red."
    assert seen == ["Which color?"]
    assert "ask_user" in offered(client)

    client = FakeClient([text("hi")])
    Session(client=client, cwd=tmp_path).send("hello")
    assert "ask_user" not in offered(client)
