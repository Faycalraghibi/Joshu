"""The Python SDK (joshu.sdk) and `joshu run --output-format/--input-format stream-json`."""

import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

sys.path.insert(0, str(Path(__file__).resolve().parent / "core"))

from test_agent_loop import FakeClient, call, text  # noqa: E402

import joshu  # noqa: E402
from joshu.sdk import Result, Session, run  # noqa: E402
from joshu.tools import filesystem_tools  # noqa: E402


@pytest.fixture
def project(tmp_path):
    (tmp_path / "calc.py").write_text("def add(a, b):\n    return a - b\n", encoding="utf-8")
    yield tmp_path
    filesystem_tools._workspace_root = None


def test_package_exports_are_lazy():
    assert joshu.Session is Session and joshu.run is run and joshu.Result is Result
    with pytest.raises(AttributeError):
        joshu.nothing_here


def test_send_returns_a_result_and_emits_events(project):
    events = []
    client = FakeClient([call("read_file", path="calc.py"), text("It subtracts.")])
    with Session(cwd=project, client=client, on_event=events.append) as session:
        result = session.send("what does add do?")

    assert result.text == "It subtracts." and result.tool_calls == 1 and result.turns == 2
    assert result.session_id == session.session_id
    assert [e["type"] for e in events] == [
        "assistant",
        "tool_use",
        "tool_result",
        "assistant",
        "result",
    ]
    assert events[0]["tool_calls"] == [{"name": "read_file", "input": {"path": "calc.py"}}]
    assert "return a - b" in events[2]["output"]
    assert events[-1]["text"] == "It subtracts."


def test_conversation_continues_across_sends(project):
    client = FakeClient([text("first"), text("second")])
    with Session(cwd=project, client=client) as session:
        session.send("one")
        session.send("two")
    user_messages = [m["content"] for m in client.requests[-1] if m["role"] == "user"]
    assert user_messages == ["one", "two"]


def test_stream_yields_events_until_the_result(project):
    client = FakeClient([call("read_file", path="calc.py"), text("done")])
    with Session(cwd=project, client=client) as session:
        events = list(session.stream("read it"))
    assert events[-1]["type"] == "result" and events[-1]["text"] == "done"
    assert any(e["type"] == "tool_use" for e in events)


def test_stream_reraises_errors(project):
    from joshu.core.llm_client import LLMError

    class Failing:
        model = "x"

        def complete(self, *args, **kwargs):
            raise LLMError("boom")

    with Session(cwd=project, client=Failing()) as session:
        with pytest.raises(LLMError, match="boom"):
            list(session.stream("x"))


def test_can_use_tool_decides_approvals(project):
    asked = []

    def can_use_tool(name, arguments):
        asked.append((name, arguments.get("path")))
        return True

    client = FakeClient(
        [
            call("replace", path="calc.py", old_string="a - b", new_string="a + b"),
            text("fixed"),
        ]
    )
    with Session(cwd=project, client=client, can_use_tool=can_use_tool) as session:
        session.send("fix it")
    assert asked == [("replace", "calc.py")]
    assert "a + b" in (project / "calc.py").read_text(encoding="utf-8")


def test_without_a_callback_approvals_are_denied(project):
    client = FakeClient(
        [call("replace", path="calc.py", old_string="a - b", new_string="a + b"), text("no")]
    )
    with Session(cwd=project, client=client) as session:
        session.send("fix it")
    assert "a - b" in (project / "calc.py").read_text(encoding="utf-8")


def test_tool_restriction(project):
    client = FakeClient([text("ok")])
    with Session(cwd=project, client=client, tools=["read_file"]) as session:
        session.send("x")
    offered = [t["function"]["name"] for t in client.tools_offered[0]]
    assert offered == ["read_file"]


def test_run_convenience(project):
    result = run("hi", cwd=project, client=FakeClient([text("hello")]))
    assert result.text == "hello"


# ---------------------------------------------------------------- the CLI


def invoke(args, client, stdin=None):
    from joshu.ui.cli import app

    with patch("joshu.core.agent.create_chat_client", return_value=client):
        return CliRunner().invoke(app, ["run", *args], input=stdin)


def events_of(output):
    return [json.loads(line) for line in output.splitlines() if line.startswith("{")]


def test_stream_json_output(project, monkeypatch):
    monkeypatch.chdir(project)
    result = invoke(
        ["--output-format", "stream-json", "what is in calc.py?"],
        FakeClient([call("read_file", path="calc.py"), text("a function")]),
    )
    events = events_of(result.stdout)
    assert result.exit_code == 0
    assert events[0]["type"] == "system" and "read_file" in events[0]["tools"]
    assert [e["type"] for e in events[1:]] == [
        "assistant",
        "tool_use",
        "tool_result",
        "assistant",
        "result",
    ]


def test_stream_json_input_runs_one_conversation(project, monkeypatch):
    monkeypatch.chdir(project)
    stdin = "\n".join(
        [
            json.dumps({"type": "user", "content": "first question"}),
            json.dumps({"type": "user", "content": [{"type": "text", "text": "second"}]}),
            "third as plain text",
        ]
    )
    client = FakeClient([text("a1"), text("a2"), text("a3")])
    result = invoke(
        ["--input-format", "stream-json", "--output-format", "stream-json"], client, stdin
    )
    results = [e["text"] for e in events_of(result.stdout) if e["type"] == "result"]
    assert results == ["a1", "a2", "a3"]
    users = [m["content"] for m in client.requests[-1] if m["role"] == "user"]
    assert users == ["first question", "second", "third as plain text"]


def test_stream_json_reports_model_errors(project, monkeypatch):
    from joshu.core.llm_client import LLMError

    monkeypatch.chdir(project)
    from joshu.ui.cli import app

    with patch("joshu.core.agent.create_chat_client", side_effect=LLMError("no key")):
        result = CliRunner().invoke(app, ["run", "--output-format", "stream-json", "hi"])
    assert result.exit_code == 1
    assert events_of(result.stdout) == [{"type": "error", "message": "no key"}]
