"""Tests for checks run on files right after the agent edits them."""

import json
import shutil
import sys

import pytest

from joshu.core.agent import Agent
from joshu.core.config import get_config_manager
from joshu.core.diagnostics import _ruff_command, check_file
from joshu.core.llm_client import AssistantTurn, ToolCall
from joshu.core.permissions import PermissionManager, PermissionMode
from joshu.tools import filesystem_tools


@pytest.fixture
def workspace(tmp_path):
    filesystem_tools.set_workspace_root(tmp_path)
    yield tmp_path
    filesystem_tools._workspace_root = None


def write(path, text):
    path.write_text(text, encoding="utf-8")
    return path


# ------------------------------------------------------------ check_file


def test_clean_and_unsupported_files_have_no_problems(tmp_path):
    assert check_file(write(tmp_path / "ok.py", "x = 1\n")) is None
    assert check_file(write(tmp_path / "ok.json", '{"a": 1}')) is None
    assert check_file(write(tmp_path / "notes.txt", "{{{ not checked")) is None
    assert check_file(tmp_path / "missing.py") is None


def test_python_syntax_error_is_reported_with_location(tmp_path):
    problems = check_file(write(tmp_path / "bad.py", "def f(:\n    pass\n"))
    assert problems.startswith("bad.py:1:")
    assert "SyntaxError" in problems


@pytest.mark.skipif(_ruff_command() is None, reason="ruff not installed")
def test_python_undefined_name_is_reported_but_style_is_not(tmp_path):
    problems = check_file(write(tmp_path / "names.py", "import os\n\nprint(undefined_thing)\n"))
    assert "F821" in problems and "undefined_thing" in problems
    assert "F401" not in problems  # unused import is style, not breakage


@pytest.mark.parametrize(
    "name,text,expected",
    [
        ("bad.json", '{"a": }', "invalid JSON"),
        ("bad.yaml", "a: [1, 2\n", "invalid YAML"),
        ("bad.toml", "a = = 1\n", "invalid TOML"),
    ],
)
def test_data_files_must_parse(tmp_path, name, text, expected):
    if name.endswith(".toml") and sys.version_info < (3, 11):
        pytest.skip("tomllib needs Python 3.11")
    assert expected in check_file(write(tmp_path / name, text))


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
def test_javascript_syntax_checked_with_node(tmp_path):
    assert check_file(write(tmp_path / "bad.js", "function (\n")) is not None
    assert check_file(write(tmp_path / "ok.js", "const a = 1;\n")) is None


def test_configured_command_overrides_and_disables(tmp_path):
    target = write(tmp_path / "main.go", "package main\n")
    fail = (
        f'"{sys.executable}" -c "import sys; print(\'bad: \' + sys.argv[1]); sys.exit(1)" {{file}}'
    )
    problems = check_file(target, {".go": fail})
    assert problems.startswith("bad: ") and "main.go" in problems

    ok = f'"{sys.executable}" -c "pass"'
    assert check_file(target, {".go": ok}) is None
    assert check_file(write(tmp_path / "bad.py", "def (:\n"), {".py": ""}) is None


# ---------------------------------------------------------------- agent


class FakeClient:
    model = "fake"

    def __init__(self, turns):
        self.turns = list(turns)

    def complete(self, messages, tools=None, **kwargs):
        return self.turns.pop(0)


def write_call(path, content):
    return AssistantTurn(
        tool_calls=[ToolCall("c1", "write_file", json.dumps({"path": path, "content": content}))]
    )


def run_write(workspace, path, content):
    agent = Agent(
        client=FakeClient([write_call(path, content), AssistantTurn(content="done")]),
        permissions=PermissionManager(PermissionMode.ACCEPT_EDITS),
        system_prompt="s",
        cwd=workspace,
    )
    agent.run("write it")
    return [m for m in agent.messages if m["role"] == "tool"][0]["content"]


def test_agent_reports_problems_after_an_edit(workspace):
    result = run_write(workspace, "broken.py", "def f(:\n")
    assert (workspace / "broken.py").exists()  # the edit itself is kept
    assert "broken.py now has problems" in result and "SyntaxError" in result


def test_agent_adds_nothing_for_a_clean_edit(workspace):
    assert "problems" not in run_write(workspace, "fine.py", "x = 1\n")


def test_diagnostics_can_be_disabled(workspace):
    get_config_manager().set("diagnostics_enabled", False)
    assert "problems" not in run_write(workspace, "broken.py", "def f(:\n")
