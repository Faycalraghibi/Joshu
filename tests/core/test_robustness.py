"""Recovering from the tool-call mistakes weaker models make."""

import json

import pytest
from test_agent_loop import FakeClient, call, make_agent, text, tool_messages

from joshu.core.agent import LOOP_STOP
from joshu.core.llm_client import AssistantTurn, ToolCall
from joshu.core.permissions import PermissionMode
from joshu.core.tool_repair import repair_arguments, resolve_tool_name
from joshu.tools import filesystem_tools
from joshu.tools.filesystem_tools import replace_tool


@pytest.fixture
def workspace(tmp_path):
    filesystem_tools.set_workspace_root(tmp_path)
    yield tmp_path
    filesystem_tools._workspace_root = None


# ------------------------------------------------------------- arguments


@pytest.mark.parametrize(
    "raw",
    [
        '{"path": "a.py"}',
        '```json\n{"path": "a.py"}\n```',
        '{"path": "a.py",}',
        "{'path': 'a.py'}",
        '{"path": "a.py"',
        '{"path": "a.py',
        'Here are the arguments: {"path": "a.py"}',
        json.dumps(json.dumps({"path": "a.py"})),
    ],
)
def test_repair_arguments(raw):
    assert repair_arguments(raw) == {"path": "a.py"}


def test_repair_keeps_nested_values_and_python_literals():
    assert repair_arguments("{'all_occurrences': True, 'n': None}") == {
        "all_occurrences": True,
        "n": None,
    }
    assert repair_arguments('{"todos": [{"text": "a"}, {"text": "b"}') == {
        "todos": [{"text": "a"}, {"text": "b"}]
    }


@pytest.mark.parametrize("raw", ["{not json", "[1, 2]", '"just text"', "path=a.py"])
def test_unrepairable_arguments_raise(raw):
    with pytest.raises(ValueError):
        repair_arguments(raw)


def test_empty_arguments_are_an_empty_object():
    assert repair_arguments("") == {} and repair_arguments(None) == {}


# ------------------------------------------------------------- tool names

TOOLS = ["read_file", "write_file", "replace", "run_shell_command", "search_file_content", "glob"]


@pytest.mark.parametrize(
    "name, expected",
    [
        ("read_file", "read_file"),
        ("ReadFile", "read_file"),
        ("functions.read_file", "read_file"),
        ("READ-FILE", "read_file"),
        ("bash", "run_shell_command"),
        ("str_replace", "replace"),
        ("grep", "search_file_content"),
        ("teleport", None),
    ],
)
def test_resolve_tool_name(name, expected):
    assert resolve_tool_name(name, TOOLS) == expected


def test_alias_only_resolves_to_offered_tools():
    assert resolve_tool_name("bash", ["read_file"]) is None


# ------------------------------------------------------------------ agent


def test_agent_runs_near_miss_tool_name_with_broken_json(workspace):
    (workspace / "a.txt").write_text("hello", encoding="utf-8")
    client = FakeClient(
        [
            AssistantTurn(
                tool_calls=[ToolCall(id="c1", name="ReadFile", arguments="{'path': 'a.txt',}")]
            ),
            text("done"),
        ]
    )
    agent = make_agent(client)
    agent.run("read it")
    assert "hello" in tool_messages(agent.messages)[0]["content"]


def test_unknown_tool_lists_available_tools(workspace):
    client = FakeClient(
        [AssistantTurn(tool_calls=[ToolCall(id="c1", name="teleport", arguments="{}")]), text("x")]
    )
    agent = make_agent(client)
    agent.run("go")
    output = tool_messages(agent.messages)[0]["content"]
    assert "Available tools:" in output and "read_file" in output


def test_missing_argument_error_lists_parameters(workspace):
    client = FakeClient([call("read_file", wrong="a.txt"), text("x")])
    agent = make_agent(client)
    agent.run("go")
    assert "Parameters: path (required)" in tool_messages(agent.messages)[0]["content"]


def test_repeated_identical_calls_warn_then_stop(workspace):
    turns = [call("read_file", call_id=f"c{i}", path="missing.txt") for i in range(10)]
    agent = make_agent(FakeClient(turns))
    response = agent.run("go")

    outputs = [m["content"] for m in tool_messages(agent.messages)]
    assert "returned the same result" not in outputs[1]
    assert "returned the same result 3 times" in outputs[2]
    assert len(outputs) == LOOP_STOP
    assert response.metadata["stopped"] == "loop"


def test_varied_calls_are_not_a_loop(workspace):
    (workspace / "a.txt").write_text("a", encoding="utf-8")
    turns = [call("read_file", call_id=f"c{i}", path="a.txt", offset=i) for i in range(6)]
    agent = make_agent(FakeClient(turns + [text("done")]), mode=PermissionMode.BYPASS)
    assert agent.run("go").metadata.get("stopped") is None


# ----------------------------------------------------------------- replace


def test_replace_keeps_crlf_line_endings(workspace):
    target = workspace / "a.py"
    target.write_bytes(b"x = 1\r\ny = 2\r\n")
    result = replace_tool("a.py", "x = 1\ny = 2", "x = 10\ny = 20")
    assert result["success"]
    assert target.read_bytes() == b"x = 10\r\ny = 20\r\n"


def test_replace_keeps_lf_line_endings(workspace):
    target = workspace / "a.py"
    target.write_bytes(b"x = 1\n")
    assert replace_tool("a.py", "x = 1", "x = 2")["success"]
    assert target.read_bytes() == b"x = 2\n"


def test_replace_applies_text_differing_only_in_indentation(workspace):
    (workspace / "a.py").write_bytes(b"def f():\n    if x:\n        return 1\n")
    result = replace_tool("a.py", "if x:\n    return 1", "if x:\n    return 2")
    assert result["success"] and "indentation" in result["note"]
    assert (workspace / "a.py").read_bytes() == b"def f():\n    if x:\n        return 2\n"


def test_replace_points_at_text_differing_only_in_indentation_when_ambiguous(workspace):
    (workspace / "a.py").write_bytes(b"def f():\n    return 1\n\ndef g():\n    return 1\n")
    result = replace_tool("a.py", "        return 1", "        return 2")  # too deep, twice
    assert not result["success"]
    assert "lines 2-2" in result["hint"].lower()


def test_replace_points_at_similar_text(workspace):
    (workspace / "a.py").write_bytes(b"def add(a, b):\n    return a - b\n")
    result = replace_tool("a.py", "def add(a,b):\n    return a-b", "x")
    assert "similar" in result["hint"]
    assert "return a - b" in result["closest_match"]


def test_replace_without_similar_text_gives_no_hint(workspace):
    (workspace / "a.py").write_bytes(b"x = 1\n")
    result = replace_tool("a.py", "completely different content here", "y")
    assert not result["success"] and "hint" not in result
