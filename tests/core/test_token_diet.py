"""Deferred MCP tools, the denial guard, compact tool results and per-request usage."""

import json
from unittest.mock import MagicMock

import pytest
from test_agent_loop import FakeClient, call, make_agent, text, tool_messages

from joshu.core import deferred_tools
from joshu.core.agent import DENIALS_STOP, DENIALS_WARN
from joshu.core.config import get_config_manager
from joshu.core.llm_client import AssistantTurn, ToolCall
from joshu.core.permissions import PermissionMode
from joshu.core.tool_executor import ToolExecutor
from joshu.core.tool_registry import ToolRegistry, ToolSpec
from joshu.tools import filesystem_tools


@pytest.fixture
def workspace(tmp_path):
    filesystem_tools.set_workspace_root(tmp_path)
    yield tmp_path
    filesystem_tools._workspace_root = None


class _Definition:
    def __init__(self, server):
        self.server_name = server


class _McpTool:
    def __init__(self, server, name):
        self.definition = _Definition(server)
        self.name = name

    def __call__(self, **kwargs):
        return {"success": True, "tool": self.name, "args": kwargs}


@pytest.fixture
def mcp_tools():
    """Register 12 fake MCP tools with long descriptions (well over the threshold)."""
    registry = ToolRegistry()
    names = [f"gh_tool_{i}" for i in range(12)]
    for name in names:
        registry.register(
            ToolSpec(
                name=name,
                description=f"GitHub operation {name}. " + "Lots of detail. " * 40,
                parameters={"type": "object", "properties": {"repo": {"type": "string"}}},
                function=_McpTool("github", name),
                requires_approval=False,
            )
        )
    yield names
    for name in names:
        registry.unregister(name) if hasattr(registry, "unregister") else registry._tools.pop(
            name, None
        )


def offered(client, index=-1):
    return [t["function"]["name"] for t in client.tools_offered[index] or []]


# ------------------------------------------------------------ deferred tools


def test_large_mcp_tool_sets_are_deferred(workspace, mcp_tools):
    client = FakeClient([text("hi")])
    agent = make_agent(client)
    agent.run("hi")

    names = offered(client)
    assert "load_tools" in names and "gh_tool_0" not in names
    assert "read_file" in names


def test_deferred_tools_are_listed_in_the_system_prompt(workspace, mcp_tools):
    from joshu.core.agent import Agent
    from joshu.core.permissions import PermissionManager

    agent = Agent(client=FakeClient([]), permissions=PermissionManager(), cwd=workspace)
    prompt = agent.messages[0]["content"]
    assert "More tools are available but not loaded" in prompt
    assert "- github: gh_tool_0" in prompt


def test_load_tools_then_call(workspace, mcp_tools):
    client = FakeClient(
        [
            AssistantTurn(
                tool_calls=[ToolCall("c1", "load_tools", json.dumps({"query": "gh_tool_3"}))]
            ),
            call("gh_tool_3", call_id="c2", repo="joshu"),
            text("done"),
        ]
    )
    agent = make_agent(client)
    agent.run("use github")

    results = tool_messages(agent.messages)
    assert '"loaded": ["gh_tool_3"]' in results[0]["content"]
    assert '"tool": "gh_tool_3"' in results[1]["content"]
    assert "gh_tool_3" in offered(client, 1) and "gh_tool_4" not in offered(client, 1)


def test_load_tools_reports_unknown_names(workspace, mcp_tools):
    client = FakeClient(
        [
            AssistantTurn(tool_calls=[ToolCall("c1", "load_tools", '{"names": ["nope"]}')]),
            text("ok"),
        ]
    )
    agent = make_agent(client)
    agent.run("x")
    assert "No matching tools" in tool_messages(agent.messages)[0]["content"]


def test_calling_a_deferred_tool_directly_works_and_loads_it(workspace, mcp_tools):
    client = FakeClient([call("gh_tool_5", repo="r"), text("ok"), text("again")])
    agent = make_agent(client)
    agent.run("x")
    assert '"tool": "gh_tool_5"' in tool_messages(agent.messages)[0]["content"]
    agent.run("y")
    assert "gh_tool_5" in offered(client)


def test_deferral_can_be_turned_off(workspace, mcp_tools):
    assert get_config_manager().set("defer_mcp_tools", False)
    try:
        client = FakeClient([text("hi")])
        make_agent(client).run("hi")
        assert "gh_tool_0" in offered(client) and "load_tools" not in offered(client)
    finally:
        get_config_manager().set("defer_mcp_tools", "auto")


def test_should_defer_modes():
    small = [MagicMock(to_openai_format=lambda: {"x": "y"})]
    assert not deferred_tools.should_defer("auto", small)
    assert deferred_tools.should_defer("always", small)
    assert not deferred_tools.should_defer(False, small)
    assert not deferred_tools.should_defer(True, [])


# -------------------------------------------------------------- denial guard


def test_repeated_denials_warn_then_stop(workspace):
    turns = [call("run_shell_command", call_id=f"c{i}", command=f"echo {i}") for i in range(10)]
    agent = make_agent(FakeClient(turns + [text("done")]), mode=PermissionMode.DEFAULT)
    response = agent.run("run things")

    outputs = [m["content"] for m in tool_messages(agent.messages)]
    assert "don't call run_shell_command again" not in outputs[DENIALS_WARN - 2]
    assert "don't call run_shell_command again" in outputs[DENIALS_WARN - 1]
    assert len(outputs) == DENIALS_STOP
    assert response.metadata["stopped"] == "denied"


def test_denials_reset_per_request(workspace):
    turns = [call("run_shell_command", command="echo 1"), text("ok")] * 2
    agent = make_agent(FakeClient(turns), mode=PermissionMode.DEFAULT)
    agent.run("a")
    agent.run("b")
    assert all("again" not in m["content"] for m in tool_messages(agent.messages))


# ----------------------------------------------------------- results & usage


def test_tool_results_are_compact_json():
    formatted = ToolExecutor(ToolRegistry()).format_result_for_llm(
        {"success": True, "result": {"path": "a.py", "lines": [1, 2]}, "error": None}
    )
    assert formatted == '{"path": "a.py", "lines": [1, 2]}'


def test_request_usage_is_per_request(workspace):
    first = AssistantTurn(content="a", usage={"prompt_tokens": 100, "completion_tokens": 5})
    second = AssistantTurn(
        content="b", usage={"prompt_tokens": 300, "completion_tokens": 7, "cached_tokens": 90}
    )
    agent = make_agent(FakeClient([first, second]))
    agent.run("one")
    meta = agent.run("two").metadata
    assert meta["request_usage"] == {
        "prompt_tokens": 300,
        "completion_tokens": 7,
        "cached_tokens": 90,
    }
    assert meta["usage"]["prompt_tokens"] == 400


def test_footer_shows_request_tokens():
    import io

    from rich.console import Console

    from joshu.core.agent import AgentResponse
    from joshu.ui.agent_ui import ConsoleAgentUI

    buffer = io.StringIO()
    ui = ConsoleAgentUI(Console(file=buffer, width=120, color_system=None))
    ui.print_footer(
        AgentResponse(
            text="",
            metadata={
                "request_usage": {
                    "prompt_tokens": 10661,
                    "completion_tokens": 43,
                    "cached_tokens": 8704,
                },
                "tool_calls": 2,
                "model": "m",
            },
        )
    )
    assert "↑ 11k in (8.7k cached) · ↓ 43 out · 2 tool calls · m" in buffer.getvalue()
