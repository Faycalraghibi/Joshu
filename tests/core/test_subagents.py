"""Tests for user-defined sub-agents."""

import json
from unittest.mock import patch

import pytest

from joshu.core.agent import Agent
from joshu.core.llm_client import AssistantTurn, ToolCall
from joshu.core.permissions import ApprovalChoice, PermissionManager, PermissionMode
from joshu.core.sessions import joshu_home
from joshu.core.subagents import discover_subagents, load_subagents
from joshu.tools import filesystem_tools


class FakeClient:
    def __init__(self, turns, model="main-model"):
        self.model = model
        self.turns = list(turns)
        self.requests = []
        self.tools_offered = []

    def complete(self, messages, tools=None, **kwargs):
        self.requests.append([dict(m) for m in messages])
        self.tools_offered.append({t["function"]["name"] for t in tools or []})
        return self.turns.pop(0)


def call(name, call_id="c1", **arguments):
    return AssistantTurn(tool_calls=[ToolCall(call_id, name, json.dumps(arguments))])


def text(content):
    return AssistantTurn(content=content)


def write(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


@pytest.fixture
def workspace(tmp_path):
    filesystem_tools.set_workspace_root(tmp_path)
    yield tmp_path
    filesystem_tools._workspace_root = None


REVIEWER = """---
description: Reviews code for bugs
tools: read_file, search_file_content
max_turns: 5
---
You are a meticulous reviewer. Report bugs only.
"""


def test_markdown_definition_is_parsed(tmp_path):
    [spec] = load_subagents(write(tmp_path / "reviewer.md", REVIEWER))
    assert spec.name == "reviewer"
    assert spec.description == "Reviews code for bugs"
    assert spec.tools == ["read_file", "search_file_content"]
    assert spec.max_turns == 5 and spec.model is None
    assert spec.system_prompt == "You are a meticulous reviewer. Report bugs only."


def test_yaml_definition_is_accepted(tmp_path):
    write(
        tmp_path / "defs.yaml",
        """
name: docwriter
description: Writes docs
prompt_config:
  system_prompt: You write documentation.
model_config:
  model_name: inherit
tool_config:
  allowed_tools: [read_file, write_file]
run_config:
  max_turns: 8
""",
    )
    [spec] = load_subagents(tmp_path / "defs.yaml")
    assert (spec.name, spec.model, spec.tools, spec.max_turns) == (
        "docwriter",
        None,
        ["read_file", "write_file"],
        8,
    )


def test_project_definitions_override_user_ones(workspace):
    write(joshu_home() / "agents" / "reviewer.md", "---\ndescription: user\n---\nuser prompt")
    write(workspace / ".joshu" / "agents" / "reviewer.md", REVIEWER)
    write(workspace / ".joshu" / "agents" / "bad name.md", "ignored")

    specs = discover_subagents(workspace)
    assert list(specs) == ["reviewer"]
    assert specs["reviewer"].description == "Reviews code for bugs"


def test_task_tool_lists_defined_agents(workspace):
    write(workspace / ".joshu" / "agents" / "reviewer.md", REVIEWER)
    agent = Agent(client=FakeClient([]), system_prompt="main", cwd=workspace)

    spec = agent._local_tools["task"].to_openai_format()["function"]
    assert spec["parameters"]["properties"]["agent"]["enum"] == ["reviewer"]
    assert "reviewer: Reviews code for bugs" in spec["description"]


def test_defined_agent_runs_with_its_prompt_and_tools(workspace):
    write(workspace / ".joshu" / "agents" / "reviewer.md", REVIEWER)
    (workspace / "app.py").write_text("x = 1 / 0\n", encoding="utf-8")
    client = FakeClient(
        [
            call("task", description="review app", prompt="review app.py", agent="reviewer"),
            call("read_file", call_id="s1", path="app.py"),  # sub-agent
            text("Division by zero on line 1."),  # sub-agent answer
            text("The reviewer found a division by zero."),
        ]
    )
    agent = Agent(client=client, system_prompt="main", cwd=workspace)

    response = agent.run("review my code")

    assert response.text == "The reviewer found a division by zero."
    sub_system = client.requests[1][0]["content"]
    assert sub_system.startswith("You are a meticulous reviewer.")
    assert client.tools_offered[1] == {"read_file", "search_file_content"}
    task_result = [m for m in agent.messages if m["role"] == "tool"][0]["content"]
    assert task_result == "Division by zero on line 1."


def test_defined_agent_with_edit_tools_uses_parent_approvals(workspace):
    write(
        workspace / ".joshu" / "agents" / "fixer.md",
        "---\ndescription: Fixes things\ntools: write_file\n---\nFix what you are told.",
    )
    asked = []

    def approver(request):
        asked.append(request.tool_name)
        return ApprovalChoice.NO

    client = FakeClient(
        [
            call("task", description="fix", prompt="create fix.txt", agent="fixer"),
            call("write_file", call_id="s1", path="fix.txt", content="x"),
            text("could not write"),
            text("done"),
        ]
    )
    agent = Agent(
        client=client,
        permissions=PermissionManager(PermissionMode.DEFAULT, approver=approver),
        system_prompt="main",
        cwd=workspace,
    )
    agent.run("fix it")

    assert asked == ["write_file"]
    assert not (workspace / "fix.txt").exists()


def test_defined_agent_can_use_another_model(workspace):
    write(
        workspace / ".joshu" / "agents" / "fast.md",
        "---\ndescription: Quick lookups\nmodel: small-model\n---\nBe brief.",
    )
    sub_client = FakeClient([text("tiny answer")], model="small-model")
    client = FakeClient([call("task", description="q", prompt="look up", agent="fast"), text("ok")])
    agent = Agent(client=client, system_prompt="main", cwd=workspace)

    with patch("joshu.core.agent.create_chat_client", return_value=sub_client) as create:
        agent.run("quick question")

    create.assert_called_once_with("small-model")
    assert sub_client.requests, "the sub-agent should use its own model"


def test_unknown_agent_name_is_reported(workspace):
    client = FakeClient([call("task", description="x", prompt="y", agent="ghost"), text("sorry")])
    agent = Agent(client=client, system_prompt="main", cwd=workspace)
    agent.run("go")

    result = [m for m in agent.messages if m["role"] == "tool"][0]["content"]
    assert "unknown agent 'ghost'" in result
