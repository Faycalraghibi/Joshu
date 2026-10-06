"""Spending limits: max_budget_usd (session cost) and max_request_tokens."""

import json

from test_agent_loop import FakeClient, make_agent, text, tool_messages

from joshu.core.llm_client import AssistantTurn, ToolCall


def listing(call_id="c1", **usage):
    return AssistantTurn(
        tool_calls=[
            ToolCall(id=call_id, name="list_directory", arguments=json.dumps({"path": "."}))
        ],
        usage=usage,
    )


def test_budget_stops_after_the_tool_round_that_spent_it(tmp_path):
    client = FakeClient([listing(cost=0.6), listing("c2", cost=0.6), text("never reached")])
    agent = make_agent(client, cwd=tmp_path, max_budget_usd=1.0)
    response = agent.run("look")
    assert response.metadata["stopped"] == "budget"
    assert "$1.00" in response.text
    assert len(client.requests) == 2
    # Every tool call has its result: the conversation can go on
    assert len(tool_messages(agent.messages)) == 2
    assert agent.messages[-1]["role"] == "assistant"


def test_a_spent_session_stops_without_calling_the_model(tmp_path):
    client = FakeClient([AssistantTurn(content="one", usage={"cost": 2.0})])
    agent = make_agent(client, cwd=tmp_path, max_budget_usd=1.0)
    assert agent.run("first").text == "one"  # a final answer is never cut
    response = agent.run("second")
    assert response.metadata["stopped"] == "budget" and len(client.requests) == 1


def test_request_token_limit_counts_this_request_only(tmp_path):
    client = FakeClient(
        [
            listing(prompt_tokens=600, completion_tokens=100),
            text("done"),
            listing("c2", prompt_tokens=600, completion_tokens=500),
            listing("c3", prompt_tokens=10, completion_tokens=10),
        ]
    )
    agent = make_agent(client, cwd=tmp_path, max_request_tokens=1000)
    assert agent.run("first").text == "done"  # 700 tokens
    response = agent.run("second")  # 1,100 tokens after one round
    assert response.metadata["stopped"] == "budget"
    assert "1,100 tokens" in response.text
    assert len(client.requests) == 3


def test_no_limits_by_default(tmp_path):
    client = FakeClient([listing(cost=50.0, prompt_tokens=10**6), text("done")])
    assert make_agent(client, cwd=tmp_path).run("look").text == "done"


def test_settings_are_the_defaults(tmp_path):
    from joshu.core.config import get_config_manager

    config = get_config_manager()
    assert config.set("max_budget_usd", 2) and config.set("max_request_tokens", 5000)
    agent = make_agent(FakeClient([]), cwd=tmp_path)
    assert (agent.max_budget_usd, agent.max_request_tokens) == (2.0, 5000)
    assert make_agent(FakeClient([]), cwd=tmp_path, max_budget_usd=0).max_budget_usd == 0
