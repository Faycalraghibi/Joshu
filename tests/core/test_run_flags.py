"""Flags of `joshu run` / `-p` that scripts and CI use (as in `claude -p`)."""

import json
from unittest.mock import patch

import pytest
from test_agent_loop import FakeClient, call, text
from typer.testing import CliRunner

from joshu.core.config import get_config_manager
from joshu.tools import filesystem_tools
from joshu.ui.run_options import (
    RunOptionError,
    apply_run_options,
    check_session_id,
    load_settings,
    tool_rules,
)


@pytest.fixture(autouse=True)
def _no_extra_dirs():
    yield
    filesystem_tools._extra_dirs.clear()


def invoke(args, client):
    from joshu.ui.cli import app

    with patch("joshu.core.agent.create_chat_client", return_value=client):
        return CliRunner().invoke(app, args)


def last_json(result):
    return json.loads(result.stdout.strip().splitlines()[-1])


# ------------------------------------------------------------------- parsing


def test_tool_rules_take_joshu_and_claude_code_names():
    assert tool_rules(["Read,Edit", "Bash(git log:*) glob", "run_shell_command(npm test)"]) == [
        "read_file",
        "replace",
        "run_shell_command(git log*)",
        "glob",
        "run_shell_command(npm test)",
    ]


def test_settings_from_json_text_or_a_file(tmp_path):
    assert load_settings('{"subagent_depth": 1}') == {"subagent_depth": 1}
    yaml_file = tmp_path / "s.yaml"
    yaml_file.write_text("self_review: false\n", encoding="utf-8")
    assert load_settings(str(yaml_file)) == {"self_review": False}
    with pytest.raises(RunOptionError):
        load_settings(str(tmp_path / "missing.json"))
    with pytest.raises(RunOptionError):
        load_settings("[1, 2]")


def test_apply_sets_rules_dirs_mcp_and_settings_for_this_run(tmp_path):
    other = tmp_path / "shared"
    other.mkdir()
    mcp = tmp_path / ".mcp.json"
    mcp.write_text(json.dumps({"mcpServers": {"docs": {"command": "docs-server"}}}), "utf-8")
    apply_run_options(
        allowed_tools=["Bash(git status:*)"],
        disallowed_tools=["WebFetch"],
        add_dirs=[str(other)],
        mcp_configs=[str(mcp)],
        settings='{"subagent_depth": 1}',
    )
    config = get_config_manager()
    assert config.get("permissions")["allow"][-1] == "run_shell_command(git status*)"
    assert config.get("permissions")["deny"][-1] == "web_fetch"
    assert other.resolve() in filesystem_tools.workspace_dirs()
    assert config.get("mcp_servers")["docs"]["command"] == "docs-server"
    assert config.get("subagent_depth") == 1
    with pytest.raises(RunOptionError):
        apply_run_options(add_dirs=[str(tmp_path / "nope")])
    with pytest.raises(RunOptionError):
        apply_run_options(mcp_configs=[str(tmp_path / "nope.json")])


def test_session_id_checks(tmp_path):
    check_session_id("ci-run-42", resuming=False, fork=False)
    with pytest.raises(RunOptionError):
        check_session_id("bad id!", resuming=False, fork=False)
    with pytest.raises(RunOptionError):
        check_session_id("ci-run-42", resuming=True, fork=False)


# ----------------------------------------------------------------------- CLI


def test_system_prompt_flags_and_max_turns(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    client = FakeClient([text("ok")])
    result = invoke(["run", "-p", "--append-system-prompt", "Answer in French.", "hi"], client)
    assert result.exit_code == 0
    system = client.requests[0][0]["content"]
    assert system.startswith("You are Joshu") and system.endswith("Answer in French.")

    client = FakeClient([text("ok")])
    invoke(["run", "-p", "--system-prompt", "You are terse.", "hi"], client)
    assert client.requests[0][0]["content"] == "You are terse."

    (tmp_path / "a.txt").write_text("a", encoding="utf-8")
    client = FakeClient([call("read_file", path="a.txt"), call("read_file", "c2", path="a.txt")])
    result = invoke(["run", "--output-format", "json", "--max-turns", "1", "loop"], client)
    assert last_json(result)["stopped"] == "max_turns"


def test_allowed_and_disallowed_tools(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    client = FakeClient([call("write_file", path="out.txt", content="x"), text("done")])
    result = invoke(["run", "-p", "--allowedTools", "Write", "make out.txt"], client)
    assert result.exit_code == 0 and (tmp_path / "out.txt").read_text() == "x"

    client = FakeClient([text("ok")])
    invoke(["run", "-p", "--disallowed-tools", "web_fetch,Bash", "hi"], client)
    offered = {t["function"]["name"] for t in client.tools_offered[0]}
    assert "web_fetch" not in offered and "run_shell_command" not in offered
    assert "read_file" in offered


def test_session_id_and_fork_session(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = invoke(
        ["run", "--output-format", "json", "--session-id", "ci-1", "remember 7"],
        FakeClient([text("ok")]),
    )
    assert last_json(result)["session_id"] == "ci-1"
    # the id is taken now
    assert invoke(["run", "-p", "--session-id", "ci-1", "x"], FakeClient([])).exit_code == 2

    client = FakeClient([text("7")])
    result = invoke(
        ["run", "--output-format", "json", "--resume", "ci-1", "--fork-session", "number?"], client
    )
    forked = last_json(result)["session_id"]
    assert forked != "ci-1" and len(client.requests[0]) == 4  # the conversation came along
    from joshu.core.sessions import load_session

    assert len(load_session("ci-1")["messages"]) == 2  # the original is unchanged


def test_bad_flag_values_exit_2(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert invoke(["run", "-p", "--add-dir", "nope", "hi"], FakeClient([])).exit_code == 2
    assert invoke(["run", "-p", "--max-turns", "0", "hi"], FakeClient([])).exit_code == 2
    assert invoke(["run", "-p", "--settings", "[1]", "hi"], FakeClient([])).exit_code == 2
