"""Read-only tool calls from one turn run at the same time."""

import threading
import time
from unittest.mock import patch

import pytest
from test_agent_loop import FakeClient, make_agent, text, tool_messages

from joshu.core.agent import Agent
from joshu.core.config import get_config_manager
from joshu.core.llm_client import AssistantTurn, ToolCall
from joshu.core.permissions import PermissionMode
from joshu.tools import filesystem_tools


@pytest.fixture
def workspace(tmp_path):
    for name in ("a", "b", "c"):
        (tmp_path / f"{name}.txt").write_text(f"content of {name}", encoding="utf-8")
    filesystem_tools.set_workspace_root(tmp_path)
    yield tmp_path
    filesystem_tools._workspace_root = None


def turn_with(*calls):
    return AssistantTurn(
        tool_calls=[ToolCall(f"c{i}", name, args) for i, (name, args) in enumerate(calls)]
    )


def slow_invoke(record):
    real = Agent._invoke

    def invoke(spec, arguments, formatter):
        record.append((threading.get_ident(), time.monotonic()))
        time.sleep(0.3)
        return real(spec, arguments, formatter)

    return invoke


def test_reads_run_concurrently_and_results_keep_order(workspace):
    record = []
    client = FakeClient(
        [
            turn_with(
                ("read_file", '{"path": "a.txt"}'),
                ("read_file", '{"path": "b.txt"}'),
                ("read_file", '{"path": "c.txt"}'),
            ),
            text("done"),
        ]
    )
    agent = make_agent(client)
    started = time.monotonic()
    with patch.object(Agent, "_invoke", staticmethod(slow_invoke(record))):
        agent.run("read all three")
    elapsed = time.monotonic() - started

    outputs = [m["content"] for m in tool_messages(agent.messages)]
    assert [
        "content of a" in outputs[0],
        "content of b" in outputs[1],
        "content of c" in outputs[2],
    ] == [True] * 3
    assert [m["tool_call_id"] for m in tool_messages(agent.messages)] == ["c0", "c1", "c2"]
    assert elapsed < 0.8  # three 0.3s calls overlapped
    assert len({thread for thread, _ in record}) > 1


def test_mixed_batches_run_one_by_one(workspace):
    record = []
    client = FakeClient(
        [
            turn_with(
                ("read_file", '{"path": "a.txt"}'),
                ("replace", '{"path": "a.txt", "old_string": "content", "new_string": "text"}'),
            ),
            text("done"),
        ]
    )
    agent = make_agent(client, mode=PermissionMode.ACCEPT_EDITS)
    with patch.object(Agent, "_invoke", staticmethod(slow_invoke(record))):
        agent.run("read then edit")
    starts = [t for _, t in record]
    assert starts[1] - starts[0] >= 0.29  # the edit started after the read finished
    assert (workspace / "a.txt").read_text(encoding="utf-8") == "text of a"


def test_protected_reads_are_not_parallel(workspace):
    (workspace / ".env").write_text("X=1", encoding="utf-8")
    agent = make_agent(FakeClient([]))
    assert not agent._parallel_safe(ToolCall("1", "read_file", '{"path": ".env"}'))
    assert agent._parallel_safe(ToolCall("2", "read_file", '{"path": "a.txt"}'))
    assert not agent._parallel_safe(ToolCall("3", "run_shell_command", '{"command": "ls"}'))
    assert not agent._parallel_safe(ToolCall("4", "read_file", "{broken"))


def test_custom_subagents_with_write_tools_run_alone(workspace):
    from joshu.core.subagents import SubagentSpec

    agent = make_agent(FakeClient([]))
    agent.subagents = {
        "reader": SubagentSpec(
            name="reader", description="r", system_prompt="p", tools=["read_file"]
        ),
        "writer": SubagentSpec(
            name="writer", description="w", system_prompt="p", tools=["replace"]
        ),
    }
    assert agent._parallel_safe(ToolCall("1", "task", '{"description": "x", "prompt": "y"}'))
    assert agent._parallel_safe(
        ToolCall("2", "task", '{"description": "x", "prompt": "y", "agent": "reader"}')
    )
    assert not agent._parallel_safe(
        ToolCall("3", "task", '{"description": "x", "prompt": "y", "agent": "writer"}')
    )


def test_can_be_turned_off(workspace):
    get_config_manager().set("parallel_tools", False)
    try:
        record = []
        client = FakeClient(
            [
                turn_with(("read_file", '{"path": "a.txt"}'), ("read_file", '{"path": "b.txt"}')),
                text("done"),
            ]
        )
        agent = make_agent(client)
        with patch.object(Agent, "_invoke", staticmethod(slow_invoke(record))):
            agent.run("x")
        assert record[1][1] - record[0][1] >= 0.29
    finally:
        get_config_manager().set("parallel_tools", True)


def test_errors_in_a_parallel_batch_are_reported_in_place(workspace):
    client = FakeClient(
        [
            turn_with(
                ("read_file", '{"path": "a.txt"}'),
                ("read_file", '{"path": "missing.txt"}'),
                ("glob", '{"pattern": "*.txt"}'),
            ),
            text("done"),
        ]
    )
    agent = make_agent(client)
    agent.run("x")
    outputs = [m["content"] for m in tool_messages(agent.messages)]
    assert "content of a" in outputs[0]
    assert "not found" in outputs[1].lower()
    assert "a.txt" in outputs[2]


def test_ui_shows_a_parallel_indicator():
    import io

    from rich.console import Console

    from joshu.ui.agent_ui import ConsoleAgentUI

    ui = ConsoleAgentUI(Console(file=io.StringIO(), force_terminal=True, width=100))
    ui.on_parallel_start(3)
    assert ui._live is not None
    ui.on_tool_start("read_file", {"path": "a.txt"})
    assert ui._live is not None  # the tool's own indicator
    ui.on_tool_end("read_file", '{"total_lines": 1}', True)
    assert ui._live is None
