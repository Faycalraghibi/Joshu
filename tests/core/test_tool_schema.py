"""Trimmed tool definitions and on-demand built-in tools."""

import json

from test_agent_loop import FakeClient, call, make_agent, text, tool_messages

from joshu.core.auto_memory import SHORT_MEMORY_GUIDE, memory_prompt
from joshu.core.tool_schema import lean_definition


def definition(name, properties, required=()):
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": "d",
            "parameters": {"type": "object", "properties": properties, "required": list(required)},
        },
    }


def test_hidden_optional_parameters_are_left_out():
    lean = lean_definition(
        definition(
            "glob",
            {
                "pattern": {
                    "type": "string",
                    "description": "Glob pattern to match (e.g., '**/*.py')",
                },
                "case_sensitive": {"type": "boolean", "description": "x"},
                "max_results": {"type": "integer", "description": "x"},
            },
            required=["pattern"],
        )
    )
    properties = lean["function"]["parameters"]["properties"]
    assert set(properties) == {"pattern"}
    assert properties["pattern"]["description"] == "e.g. **/*.py"


def test_required_parameters_are_never_hidden():
    lean = lean_definition(
        definition("glob", {"max_results": {"type": "integer"}}, required=["max_results"])
    )
    assert "max_results" in lean["function"]["parameters"]["properties"]


def test_other_tools_get_shortened_descriptions():
    long = "Do something useful (default: 10) " + "with many many words " * 10
    lean = lean_definition(definition("mcp_tool", {"x": {"type": "string", "description": long}}))
    text_ = lean["function"]["parameters"]["properties"]["x"]["description"]
    assert "(default" not in text_ and len(text_) <= 81 and text_.endswith("…")


def test_original_definition_is_not_modified():
    original = definition("glob", {"max_results": {"type": "integer"}})
    snapshot = json.dumps(original)
    lean_definition(original)
    assert json.dumps(original) == snapshot


def test_rare_builtins_load_on_demand(tmp_path):
    from joshu.tools import filesystem_tools

    filesystem_tools.set_workspace_root(tmp_path)
    try:
        client = FakeClient([text("hi")])
        agent = make_agent(client)
        agent.run("hi")
        offered = [t["function"]["name"] for t in client.tools_offered[-1]]
        assert "web_search" not in offered and "bash_output" not in offered
        assert "load_tools" in offered and "read_file" in offered
        # Sent definitions are the trimmed ones
        glob = next(t for t in client.tools_offered[-1] if t["function"]["name"] == "glob")
        assert "max_results" not in glob["function"]["parameters"]["properties"]
    finally:
        filesystem_tools._workspace_root = None


def test_background_command_loads_bash_output(tmp_path, monkeypatch):
    from joshu.core.permissions import PermissionMode
    from joshu.tools import filesystem_tools, shell_tool

    filesystem_tools.set_workspace_root(tmp_path)
    monkeypatch.setattr(
        shell_tool,
        "start_background_process",
        lambda *a, **k: {"success": True, "process_id": "p1"},
    )
    try:
        client = FakeClient(
            [call("run_shell_command", command="npm run dev", background=True), text("started")]
        )
        agent = make_agent(client, mode=PermissionMode.BYPASS)
        agent.run("start the server")
        offered = [t["function"]["name"] for t in client.tools_offered[-1]]
        assert "bash_output" in offered and "kill_bash" in offered
        assert "p1" in tool_messages(agent.messages)[0]["content"]
    finally:
        filesystem_tools._workspace_root = None


def test_memory_guide_is_short_without_memories(tmp_path):
    (tmp_path / ".git").mkdir()
    assert memory_prompt(tmp_path) == SHORT_MEMORY_GUIDE
