"""session_start, stop, subagent_stop, pre_compress, notification, session_end and
context injection from hooks."""

import sys

import pytest
from test_agent_loop import FakeClient, call, make_agent, text

from joshu.core.permissions import ApprovalChoice, PermissionManager, PermissionMode
from joshu.hooks.dispatcher import configure_hooks_from_settings, get_hook_dispatcher
from joshu.hooks.events import HookEvent
from joshu.hooks.schemas import HookResponse
from joshu.tools import filesystem_tools


@pytest.fixture(autouse=True)
def clean_hooks(tmp_path):
    dispatcher = get_hook_dispatcher()
    dispatcher.clear()
    filesystem_tools.set_workspace_root(tmp_path)
    yield dispatcher
    dispatcher.clear()
    filesystem_tools._workspace_root = None


def record(dispatcher, event, response=None):
    """Register a Python hook that records payloads (and optionally answers)."""
    seen = []

    def handler(payload):
        seen.append(payload.data)
        return response or HookResponse()

    dispatcher.register_python_hook(event, handler)
    return seen


def python_command(code):
    return f'"{sys.executable}" -c "{code}"'


def first_user_message(agent):
    return next(m["content"] for m in agent.messages if m["role"] == "user")


# -------------------------------------------------------------- context


def test_session_start_stdout_becomes_context_once(clean_hooks):
    problems = configure_hooks_from_settings(
        {"session_start": [python_command("print('Today the deploy is frozen')")]}
    )
    assert problems == []
    agent = make_agent(FakeClient([text("a"), text("b")]))
    agent.run("first")
    agent.run("second")

    assert "Today the deploy is frozen" in first_user_message(agent)
    user_messages = [m["content"] for m in agent.messages if m["role"] == "user"]
    assert "frozen" not in user_messages[1]


def test_before_agent_json_context(clean_hooks):
    configure_hooks_from_settings(
        {
            "before_agent": [
                python_command(
                    "import json; print(json.dumps({'additional_context': 'Current branch: x'}))"
                )
            ]
        }
    )
    record(clean_hooks, HookEvent.BEFORE_AGENT, HookResponse(additional_context="Ticket: ABC-1"))
    agent = make_agent(FakeClient([text("ok")]))
    agent.run("do it")
    content = first_user_message(agent)
    assert content.startswith("[Context from hooks]")
    assert "Ticket: ABC-1" in content and "Current branch: x" in content
    assert content.rstrip().endswith("do it")


# -------------------------------------------------------------------- stop


def test_stop_hook_sends_the_agent_back_to_work(clean_hooks):
    answers = iter(["block", "allow"])
    seen = record(clean_hooks, HookEvent.STOP)
    clean_hooks._python_hooks[HookEvent.STOP] = [
        lambda payload: (
            seen.append(payload.data)
            or HookResponse(action=next(answers), message="Run the tests first.")
        )
    ]
    client = FakeClient([text("done?"), text("tests pass, done")])
    response = make_agent(client).run("fix it")

    assert response.text == "tests pass, done"
    assert any(m.get("content") == "[Stop hook] Run the tests first." for m in client.requests[-1])
    assert seen[0]["response"] == "done?" and seen[1]["continues_so_far"] == 1


def test_stop_hook_cannot_loop_forever(clean_hooks):
    record(clean_hooks, HookEvent.STOP, HookResponse(action="block", message="again"))
    client = FakeClient([text(f"reply {i}") for i in range(10)])
    response = make_agent(client).run("x")
    assert response.text == "reply 3"  # three continues, then it finishes


def test_stop_hook_via_exit_code_2(clean_hooks):
    configure_hooks_from_settings(
        {
            "stop": [
                python_command(
                    "import sys,json; d=json.load(sys.stdin)['data']; "
                    "sys.exit(2 if d['continues_so_far'] == 0 else 0)"
                )
            ]
        }
    )
    client = FakeClient([text("first"), text("second")])
    assert make_agent(client).run("x").text == "second"


# ---------------------------------------------------------- other events


def test_subagent_stop_fires(clean_hooks):
    seen = record(clean_hooks, HookEvent.SUBAGENT_STOP)
    client = FakeClient(
        [
            call("task", description="look around", prompt="find things"),
            text("sub-agent result"),
            text("done"),
        ]
    )
    make_agent(client).run("delegate")
    assert seen == [{"description": "look around", "response": "sub-agent result"}]


def test_pre_compress_can_block_clearing(clean_hooks, tmp_path, monkeypatch):
    from joshu.core import context_editing
    from joshu.core.config import get_config_manager

    monkeypatch.setattr(context_editing, "MIN_FREED_TOKENS", 100)
    seen = record(clean_hooks, HookEvent.PRE_COMPRESS, HookResponse(action="block"))
    for i in range(10):
        (tmp_path / f"f{i}.txt").write_text("x" * 3000, encoding="utf-8")
    get_config_manager().set("clear_tool_results_at", 2000)
    try:
        turns = [call("read_file", call_id=f"c{i}", path=f"f{i}.txt") for i in range(10)]
        agent = make_agent(FakeClient(turns + [text("done")]), mode=PermissionMode.PLAN)
        agent.run("read")
    finally:
        get_config_manager().set("clear_tool_results_at", 60000)
    assert seen and seen[0]["kind"] == "clear"
    assert not any("[Cleared" in str(m.get("content")) for m in agent.messages)


def test_notification_fires_when_approval_is_needed(clean_hooks):
    seen = record(clean_hooks, HookEvent.NOTIFICATION)
    manager = PermissionManager(PermissionMode.DEFAULT, approver=lambda r: ApprovalChoice.NO)
    manager.check("run_shell_command", {"command": "npm install"}, True)
    assert seen and seen[0]["tool_name"] == "run_shell_command"
    assert "approval" in seen[0]["message"]


def test_session_end_on_reset_and_end(clean_hooks):
    seen = record(clean_hooks, HookEvent.SESSION_END)
    agent = make_agent(FakeClient([text("a"), text("b")]))
    agent.end_session()
    assert seen == []  # nothing started yet
    agent.run("one")
    first_id = agent.session_id
    agent.reset()
    assert len(seen) == 1
    agent.run("two")
    agent.end_session()
    agent.end_session()  # only once
    assert len(seen) == 2 and agent.session_id != first_id


def test_new_events_are_configurable(clean_hooks):
    assert configure_hooks_from_settings({"stop": ["x"], "subagent_stop": ["y"]}) == []
