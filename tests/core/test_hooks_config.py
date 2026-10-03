"""Tests for hooks configured in config.yaml and fired by the agent."""

import json
import sys
from pathlib import Path

import pytest

from joshu.core.agent import Agent
from joshu.core.llm_client import AssistantTurn, ToolCall
from joshu.core.permissions import PermissionManager, PermissionMode
from joshu.hooks import HookEvent, configure_hooks_from_settings, get_hook_dispatcher
from joshu.tools import filesystem_tools


@pytest.fixture(autouse=True)
def clean_dispatcher():
    get_hook_dispatcher().clear()
    yield
    get_hook_dispatcher().clear()


@pytest.fixture
def workspace(tmp_path):
    filesystem_tools.set_workspace_root(tmp_path)
    yield tmp_path
    filesystem_tools._workspace_root = None


class FakeClient:
    model = "fake"

    def __init__(self, turns):
        self.turns = list(turns)

    def complete(self, messages, tools=None, **kwargs):
        return self.turns.pop(0)


def read_call(path):
    return AssistantTurn(tool_calls=[ToolCall("c1", "read_file", json.dumps({"path": path}))])


def hook_script(directory: Path, name: str, body: str) -> str:
    """Write a Python hook script and return a shell command that runs it."""
    script = directory / name
    script.write_text("import json, sys\npayload = json.load(sys.stdin)\n" + body, encoding="utf-8")
    return f'"{sys.executable}" "{script}"'


def make_agent(client, workspace):
    return Agent(
        client=client,
        permissions=PermissionManager(PermissionMode.DEFAULT),
        system_prompt="test",
        cwd=workspace,
    )


def tool_output(agent):
    return [m for m in agent.messages if m["role"] == "tool"][0]["content"]


def test_before_tool_hook_blocks_with_reason(workspace, tmp_path):
    (workspace / "secret.txt").write_text("s3cret", encoding="utf-8")
    command = hook_script(
        tmp_path,
        "block.py",
        "if 'secret' in payload['data']['arguments'].get('path', ''):\n"
        "    print('secret files are off limits', file=sys.stderr)\n"
        "    sys.exit(2)\n",
    )
    assert configure_hooks_from_settings({"before_tool": [command]}) == []

    agent = make_agent(
        FakeClient([read_call("secret.txt"), AssistantTurn(content="ok")]), workspace
    )
    agent.run("read the secret")

    assert tool_output(agent) == "Blocked by hook: secret files are off limits"


def test_before_tool_hook_can_rewrite_arguments(workspace, tmp_path):
    (workspace / "real.txt").write_text("the real one", encoding="utf-8")
    command = hook_script(
        tmp_path,
        "rewrite.py",
        "print(json.dumps({'action': 'modify',"
        " 'modified_data': {'arguments': {'path': 'real.txt'}}}))\n",
    )
    configure_hooks_from_settings({"before_tool": [{"command": command, "timeout": 20}]})

    agent = make_agent(FakeClient([read_call("decoy.txt"), AssistantTurn(content="ok")]), workspace)
    agent.run("read decoy")

    assert "the real one" in tool_output(agent)


def test_after_tool_and_after_agent_hooks_receive_payloads(workspace, tmp_path):
    (workspace / "a.txt").write_text("hello", encoding="utf-8")
    log = tmp_path / "events.log"
    command = hook_script(
        tmp_path,
        "log.py",
        f"open(r'{log}', 'a').write(payload['event'] + '\\n')\n",
    )
    configure_hooks_from_settings({"after_tool": command, "after_agent": [command]})

    agent = make_agent(FakeClient([read_call("a.txt"), AssistantTurn(content="done")]), workspace)
    agent.run("read a")

    assert log.read_text().split() == ["after_tool", "after_agent"]


def test_python_script_path_runs_with_current_interpreter(tmp_path):
    script = tmp_path / "hook.py"
    script.write_text("import sys\nsys.stdin.read()\nsys.exit(2)\n", encoding="utf-8")
    get_hook_dispatcher().register_hook(HookEvent.BEFORE_TOOL, script)

    from joshu.hooks.dispatcher import dispatch_before_tool

    assert dispatch_before_tool("s", "read_file", {}).should_block


def test_invalid_entries_are_reported_and_reconfiguring_replaces_hooks(tmp_path):
    problems = configure_hooks_from_settings(
        {"before_lunch": ["echo hi"], "before_tool": [42], "after_tool": "echo ok"}
    )
    assert any("unknown hook event 'before_lunch'" in p for p in problems)
    assert any("invalid entry 42" in p for p in problems)
    assert len(get_hook_dispatcher().list_hooks()["after_tool"]) == 1

    configure_hooks_from_settings({})
    assert not any(get_hook_dispatcher().list_hooks().values())
