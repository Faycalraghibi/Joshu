"""Shell commands with unbalanced quotes must not crash the safety check or the request."""

import json

import pytest

from joshu.core.agent import Agent
from joshu.core.llm_client import AssistantTurn, ToolCall
from joshu.core.lsp import find_command
from joshu.core.permissions import PermissionManager, PermissionMode
from joshu.core.safety import assess_command_safety


@pytest.mark.parametrize(
    "command",
    ["echo don't panic", 'python -c "print(1)', "grep 'unterminated src"],
)
def test_safety_check_handles_unbalanced_quotes(command):
    report = assess_command_safety(command)
    assert report.safe in (True, False)


@pytest.mark.parametrize("command", ["rm -rf / oops", "format C: now", "del /s /q C:\\ now"])
def test_unbalanced_quote_does_not_change_the_verdict(command):
    """The OS-specific rules decide; a stray quote must not make a command look safe."""
    assert assess_command_safety(command + " 'x").safe == assess_command_safety(command).safe


def test_agent_survives_a_command_with_an_unbalanced_quote(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    class Client:
        model = "fake"

        def __init__(self):
            self.turns = [
                AssistantTurn(
                    tool_calls=[
                        ToolCall(
                            id="c1",
                            name="run_shell_command",
                            arguments=json.dumps({"command": "echo don't panic"}),
                        )
                    ]
                ),
                AssistantTurn(content="done", finish_reason="stop"),
            ]

        def complete(self, messages, tools=None, **kwargs):
            return self.turns.pop(0)

    agent = Agent(
        permissions=PermissionManager(PermissionMode.BYPASS), client=Client(), persist=False
    )
    assert agent.run("say it").text == "done"
    assert any(m.get("role") == "tool" for m in agent.messages)


def test_lsp_setting_with_unbalanced_quote_does_not_crash():
    assert find_command("python", {"python": 'pylsp "--verbose'}) in (None, ["pylsp", "--verbose"])
