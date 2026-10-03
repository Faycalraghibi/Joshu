"""Tests for cost tracking."""

import json
from types import SimpleNamespace

from joshu.core.agent import Agent
from joshu.core.config import get_config_manager
from joshu.core.costs import CostTracker, format_cost, request_cost
from joshu.core.llm_client import AssistantTurn, ToolCall, _usage_dict
from joshu.core.permissions import PermissionManager, PermissionMode
from joshu.core.providers import BUILTIN_PROVIDERS
from joshu.core.sessions import load_session


class FakeClient:
    def __init__(self, turns, model="m"):
        self.model = model
        self.turns = list(turns)

    def complete(self, messages, tools=None, **kwargs):
        return self.turns.pop(0)


def turn(content="ok", tool_calls=None, **usage):
    return AssistantTurn(content=content, tool_calls=tool_calls or [], usage=usage)


def make_agent(client, tmp_path, **kwargs):
    return Agent(
        client=client,
        permissions=PermissionManager(PermissionMode.PLAN),
        system_prompt="s",
        cwd=tmp_path,
        **kwargs,
    )


def test_reported_cost_wins_over_pricing():
    usage = {"prompt_tokens": 1000, "completion_tokens": 1000, "cost": 0.5}
    assert request_cost(usage, "m", {"m": {"input": 1, "output": 1}}) == 0.5


def test_cost_from_pricing_per_million_tokens():
    usage = {"prompt_tokens": 2_000_000, "completion_tokens": 500_000}
    assert request_cost(usage, "m", {"m": {"input": 0.4, "output": 1.6}}) == 0.8 + 0.8


def test_unknown_price_is_none_not_zero():
    assert request_cost({"prompt_tokens": 10}, "m", {}) is None
    tracker = CostTracker()
    tracker.add(0.01)
    tracker.add(None)
    assert not tracker.known
    assert format_cost(tracker) == "at least $0.0100 (some prices unknown)"
    assert format_cost(CostTracker()) == "$0.0000"


def test_usage_dict_reads_provider_cost_from_extra_fields():
    usage = SimpleNamespace(
        prompt_tokens=10, completion_tokens=5, total_tokens=15, model_extra={"cost": 0.002}
    )
    assert _usage_dict(usage)["cost"] == 0.002
    plain = SimpleNamespace(prompt_tokens=1, completion_tokens=1, total_tokens=2)
    assert "cost" not in _usage_dict(plain)


def test_openrouter_requests_cost_accounting():
    assert BUILTIN_PROVIDERS["openrouter"].request_options == {"usage": {"include": True}}


def test_agent_sums_cost_across_turns_and_reports_it(tmp_path):
    (tmp_path / "a.txt").write_text("x", encoding="utf-8")
    read = ToolCall("c1", "read_file", json.dumps({"path": "a.txt"}))
    client = FakeClient(
        [
            turn("", [read], prompt_tokens=100, completion_tokens=10, cost=0.001),
            turn("done", prompt_tokens=200, completion_tokens=20, cost=0.002),
        ]
    )
    from joshu.tools import filesystem_tools

    filesystem_tools.set_workspace_root(tmp_path)
    try:
        response = make_agent(client, tmp_path).run("read a")
    finally:
        filesystem_tools._workspace_root = None

    assert response.metadata["cost_usd"] == 0.003


def test_agent_cost_is_unknown_without_price(tmp_path):
    client = FakeClient([turn("hi", prompt_tokens=5, completion_tokens=5)])
    assert make_agent(client, tmp_path).run("hi").metadata["cost_usd"] is None


def test_model_pricing_from_config(tmp_path):
    get_config_manager().set("model_pricing", {"priced": {"input": 1.0, "output": 2.0}})
    client = FakeClient(
        [turn("hi", prompt_tokens=1_000_000, completion_tokens=1_000_000)], model="priced"
    )
    assert make_agent(client, tmp_path).run("hi").metadata["cost_usd"] == 3.0


def test_subagent_cost_is_included(tmp_path):
    task = ToolCall("t1", "task", json.dumps({"description": "d", "prompt": "p"}))
    client = FakeClient(
        [
            turn("", [task], cost=0.01),
            turn("sub answer", cost=0.02),  # sub-agent
            turn("final", cost=0.03),
        ]
    )
    assert make_agent(client, tmp_path).run("go").metadata["cost_usd"] == 0.06


def test_cost_is_saved_and_restored(tmp_path):
    first = make_agent(FakeClient([turn("a", cost=0.25)]), tmp_path, persist=True)
    first.run("one")

    second = make_agent(FakeClient([turn("b", cost=0.5)]), tmp_path)
    second.restore(load_session(first.session_id))
    assert second.run("two").metadata["cost_usd"] == 0.75
