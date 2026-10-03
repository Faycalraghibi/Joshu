"""A2A tasks driven by the tool-using agent."""

import asyncio
import json

import pytest

from joshu.a2a.event_bus import ExecutionEventBus
from joshu.a2a.events import EventType
from joshu.a2a.executor import AgentExecutor
from joshu.a2a.task import AgentSettings, TaskState
from joshu.a2a.task_store import InMemoryTaskStore
from joshu.core.llm_client import AssistantTurn, LLMError, ToolCall
from joshu.tools import filesystem_tools


class FakeClient:
    """Scripted model; streams text through on_text like the real client."""

    model = "fake"

    def __init__(self, turns):
        self.turns = list(turns)

    def complete(self, messages, tools=None, *, on_text=None, **kwargs):
        turn = self.turns.pop(0)
        if on_text and turn.content:
            on_text(turn.content)
        return turn


def call(name, call_id="c1", say="", **arguments):
    """A model turn that calls a tool; `say` is the text written before it."""
    return AssistantTurn(content=say, tool_calls=[ToolCall(call_id, name, json.dumps(arguments))])


def text(content):
    return AssistantTurn(content=content)


@pytest.fixture(autouse=True)
def reset_workspace():
    yield
    filesystem_tools._workspace_root = None


def run_task(tmp_path, turns, answer=None, approval_mode="safe_only", factory=None):
    """Create and execute a task; answer confirmation requests with `answer`."""
    executor = AgentExecutor(
        task_store=InMemoryTaskStore(),
        event_bus=ExecutionEventBus(),
        client_factory=factory or (lambda settings: FakeClient(turns)),
    )

    async def drive():
        settings = AgentSettings(target_directory=str(tmp_path), approval_mode=approval_mode)
        task = await executor.create_task("do the thing", settings)
        events = []
        async for event in executor.execute_task(task.task_id):
            events.append(event)
            if event.event_type == EventType.CONFIRMATION_REQUEST and answer:
                await executor.respond_to_confirmation(task.task_id, event.data["call_id"], answer)
        return events, await executor.get_task(task.task_id)

    return asyncio.run(asyncio.wait_for(drive(), timeout=30))


def of_type(events, event_type):
    return [e for e in events if e.event_type == event_type]


def test_task_runs_the_agent_and_completes(tmp_path):
    (tmp_path / "notes.txt").write_text("forty-two", encoding="utf-8")
    events, task = run_task(
        tmp_path, [call("read_file", path="notes.txt"), text("The notes say forty-two.")]
    )

    tool_events = [e.data for e in of_type(events, EventType.TOOL_CALL)]
    assert [(t["tool_name"], t["status"]) for t in tool_events] == [
        ("read_file", "executing"),
        ("read_file", "completed"),
    ]
    assert "forty-two" in tool_events[1]["result"]
    assert of_type(events, EventType.MESSAGE)[0].data["content"] == "The notes say forty-two."
    assert of_type(events, EventType.COMPLETE)[0].data["result"] == "The notes say forty-two."
    assert task.state == TaskState.COMPLETED


def test_text_before_a_tool_call_is_a_thought(tmp_path):
    (tmp_path / "a.txt").write_text("x", encoding="utf-8")
    events, _ = run_task(
        tmp_path, [call("read_file", say="Let me look.", path="a.txt"), text("done")]
    )
    assert of_type(events, EventType.THOUGHT)[0].data["content"] == "Let me look."


def test_approved_edit_is_applied(tmp_path):
    events, task = run_task(
        tmp_path,
        [call("write_file", path="new.txt", content="hello"), text("written")],
        answer="proceed_once",
    )
    request = of_type(events, EventType.CONFIRMATION_REQUEST)[0].data
    assert request["tool_name"] == "write_file" and "new.txt" in request["description"]
    assert (tmp_path / "new.txt").read_text(encoding="utf-8") == "hello"
    assert task.state == TaskState.COMPLETED


def test_denied_edit_is_not_applied(tmp_path):
    events, task = run_task(
        tmp_path,
        [call("write_file", path="new.txt", content="hello"), text("ok, I won't")],
        answer="cancel",
    )
    assert not (tmp_path / "new.txt").exists()
    failed = [e.data for e in of_type(events, EventType.TOOL_CALL) if e.data["status"] == "failed"]
    assert "denied" in failed[0]["error"]
    assert task.state == TaskState.COMPLETED


def test_cancel_task_from_a_confirmation_stops_the_agent(tmp_path):
    events, task = run_task(
        tmp_path,
        [call("write_file", path="new.txt", content="x"), text("should not get here")],
        answer="cancel_task",
    )
    assert not (tmp_path / "new.txt").exists()
    assert task.state == TaskState.CANCELED
    assert not of_type(events, EventType.COMPLETE)


def test_bypass_mode_needs_no_confirmation(tmp_path):
    events, _ = run_task(
        tmp_path,
        [call("write_file", path="new.txt", content="x"), text("done")],
        approval_mode="bypass",
    )
    assert not of_type(events, EventType.CONFIRMATION_REQUEST)
    assert (tmp_path / "new.txt").exists()


def test_model_errors_fail_the_task(tmp_path):
    def broken(settings):
        raise LLMError("Provider 'openrouter' needs an API key: set OPENROUTER_API_KEY.")

    events, task = run_task(tmp_path, [], factory=broken)
    assert "OPENROUTER_API_KEY" in of_type(events, EventType.ERROR)[0].data["error"]
    assert task.state == TaskState.FAILED


# --------------------------------------------------------------- server


def test_server_requires_the_token_and_allows_no_cross_origin_by_default(monkeypatch):
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    from joshu.a2a.server import app

    monkeypatch.setenv("JOSHU_A2A_TOKEN", "s3cret")
    client = TestClient(app)

    assert client.get("/health").status_code == 200
    assert client.get("/.well-known/agent-card.json").status_code == 200
    assert client.get("/tasks/metadata").status_code == 401
    assert (
        client.get("/tasks/metadata", headers={"Authorization": "Bearer wrong"}).status_code == 401
    )
    assert (
        client.get("/tasks/metadata", headers={"Authorization": "Bearer s3cret"}).status_code == 200
    )

    response = client.get("/health", headers={"Origin": "https://evil.example"})
    assert "access-control-allow-origin" not in response.headers


def test_server_refuses_everything_without_a_configured_token(monkeypatch):
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    from joshu.a2a.server import app

    monkeypatch.delenv("JOSHU_A2A_TOKEN", raising=False)
    response = TestClient(app).get("/tasks/metadata", headers={"Authorization": "Bearer "})
    assert response.status_code == 401


def test_task_over_http_streams_the_agent_run(tmp_path, monkeypatch):
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    from joshu.a2a import server

    (tmp_path / "a.txt").write_text("hello from a", encoding="utf-8")
    executor = AgentExecutor(
        task_store=InMemoryTaskStore(),
        event_bus=ExecutionEventBus(),
        client_factory=lambda settings: FakeClient(
            [call("read_file", path="a.txt"), text("It says hello.")]
        ),
    )
    monkeypatch.setattr(server, "get_agent_executor", lambda: executor)
    monkeypatch.setenv("JOSHU_A2A_TOKEN", "t")
    client = TestClient(server.app)
    auth = {"Authorization": "Bearer t"}

    created = client.post(
        "/tasks",
        json={"message": "read a.txt", "target_directory": str(tmp_path), "approval_mode": "plan"},
        headers=auth,
    )
    assert created.status_code == 200
    task_id = created.json()["task_id"]

    stream = client.get(f"/tasks/{task_id}/stream", headers=auth)
    names = [
        line[len("event: ") :] for line in stream.text.splitlines() if line.startswith("event: ")
    ]
    assert names[-2:] == ["message", "complete"]
    assert "tool_call" in names
    assert "It says hello." in stream.text
