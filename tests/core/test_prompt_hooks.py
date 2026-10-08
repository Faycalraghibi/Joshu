"""Prompt hooks: a model decides whether an event goes ahead."""

import json

import pytest

from joshu.core.claude_compat import read_hooks_json
from joshu.core.llm_client import AssistantTurn
from joshu.hooks import prompt_hooks
from joshu.hooks.dispatcher import (
    configure_hooks_from_settings,
    dispatch_before_tool,
    dispatch_stop,
    get_hook_dispatcher,
)


class FakeModel:
    def __init__(self, reply=None, error=None):
        self.reply, self.error, self.seen = reply, error, []

    def complete(self, messages, **kwargs):
        self.seen.append(messages)
        if self.error:
            raise self.error
        return AssistantTurn(content=self.reply)


@pytest.fixture
def model(monkeypatch):
    fake = FakeModel('{"ok": true}')
    monkeypatch.setattr(prompt_hooks, "_hook_client", lambda: fake)
    yield fake
    get_hook_dispatcher().clear_script_hooks()


def with_hook(prompt="Refuse commands that delete files: $ARGUMENTS", matcher=None):
    entry = {"prompt": prompt, **({"matcher": matcher} if matcher else {})}
    assert configure_hooks_from_settings({"before_tool": [entry]}) == []


def test_ok_false_blocks_with_the_reason(model):
    model.reply = 'Sure. {"ok": false, "reason": "rm -rf deletes the project"}'
    with_hook()
    result = dispatch_before_tool("s", "run_shell_command", {"command": "rm -rf ."})
    assert result.should_block and result.response.message == "rm -rf deletes the project"
    sent = model.seen[0][1]["content"]
    assert '"tool_name": "Bash"' in sent and "$ARGUMENTS" not in sent  # the event, in its place


def test_ok_true_and_bad_answers_let_it_go(model):
    with_hook(prompt="Allow everything")
    assert not dispatch_before_tool("s", "read_file", {"path": "a"}).should_block
    assert "Event:" in model.seen[0][1]["content"]  # no $ARGUMENTS: appended
    model.reply = "I think it's fine"
    assert not dispatch_before_tool("s", "read_file", {"path": "a"}).should_block
    model.error = RuntimeError("model down")
    assert not dispatch_before_tool("s", "read_file", {"path": "a"}).should_block


def test_matcher_and_stop(model):
    with_hook(matcher="Bash")
    dispatch_before_tool("s", "read_file", {"path": "a"})
    assert model.seen == []  # not a Bash call: the model isn't asked
    model.reply = '{"ok": false, "reason": "run the tests first"}'
    assert configure_hooks_from_settings({"stop": [{"prompt": "Were tests run?"}]}) == []
    result = dispatch_stop("s", "fix it", "done", 0)
    assert result.should_block and result.response.message == "run the tests first"


def test_claude_code_prompt_hooks_are_read(tmp_path):
    hooks = tmp_path / "hooks.json"
    stop = [{"hooks": [{"type": "prompt", "prompt": "Done? $ARGUMENTS", "timeout": 30}]}]
    pre = [{"matcher": "Bash", "hooks": [{"type": "prompt", "prompt": "Safe?"}]}]
    hooks.write_text(json.dumps({"hooks": {"Stop": stop, "PreToolUse": pre}}), encoding="utf-8")
    read = read_hooks_json(hooks, tmp_path)
    assert read["stop"] == [{"prompt": "Done? $ARGUMENTS", "timeout": 30}]
    assert read["before_tool"] == [{"prompt": "Safe?", "matcher": "Bash"}]


def test_decision_parsing():
    assert prompt_hooks.decision('{"ok": true}') == {"ok": True}
    assert prompt_hooks.decision('text {"ok": false, "reason": "x"} more') == {
        "ok": False,
        "reason": "x",
    }
    assert prompt_hooks.decision("no json") is None
    assert prompt_hooks.decision('{"other": 1}') is None
