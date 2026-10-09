"""Sub-agents that start their own sub-agents, down to the subagent_depth setting."""

import pytest
from test_agent_loop import FakeClient, call, make_agent, text, tool_messages

from joshu.core.config import get_config_manager
from joshu.tools import filesystem_tools


@pytest.fixture
def workspace(tmp_path):
    filesystem_tools.set_workspace_root(tmp_path)
    yield tmp_path
    filesystem_tools._workspace_root = None


def offered(tools):
    return {t["function"]["name"] for t in tools or []}


def test_a_sub_agent_delegates_one_level_down(workspace):
    client = FakeClient(
        [
            call("task", description="survey", prompt="survey the repo"),  # main
            call("task", "c2", description="auth part", prompt="look at auth"),  # level 1
            text("auth lives in auth.py"),  # level 2
            text("survey: auth lives in auth.py"),  # level 1
            text("Done."),  # main
        ]
    )
    agent = make_agent(client)
    agent.run("survey this")
    assert "survey: auth lives in auth.py" in tool_messages(agent.messages)[0]["content"]
    # requests: main, level 1, level 2, level 1, main
    assert "task" in offered(client.tools_offered[1])  # level 1 may delegate
    assert "task" not in offered(client.tools_offered[2])  # level 2 (the limit) may not


def test_depth_one_keeps_sub_agents_from_delegating(workspace):
    get_config_manager().set("subagent_depth", 1)
    try:
        client = FakeClient(
            [call("task", description="survey", prompt="survey"), text("found"), text("Done.")]
        )
        make_agent(client).run("survey this")
        assert "task" in offered(client.tools_offered[0])
        assert "task" not in offered(client.tools_offered[1])
    finally:
        get_config_manager().set("subagent_depth", 2)


def test_a_sub_agent_cant_start_an_editing_one(workspace):
    client = FakeClient(
        [
            call("task", description="survey", prompt="survey"),
            call("task", "c2", description="fix", prompt="fix it", edit=True),
            text("couldn't"),
            text("Done."),
        ]
    )
    agent = make_agent(client)
    agent.run("go")
    level_one = client.requests[2]  # level 1's second request holds its task result
    assert any("only start read-only sub-agents" in str(m.get("content")) for m in level_one)
    task = next(t for t in client.tools_offered[1] if t["function"]["name"] == "task")
    assert "edit" not in task["function"]["parameters"]["properties"]


def test_read_only_sub_agents_get_only_what_they_may_use(workspace):
    client = FakeClient([call("task", description="look", prompt="look"), text("x"), text("Done.")])
    make_agent(client).run("look around")
    sub = offered(client.tools_offered[1])
    assert {"read_file", "glob", "search_file_content", "task"} <= sub
    # denied in plan mode: offered, they were called and the denials ended the sub-agent
    assert not sub & {"run_shell_command", "write_file", "replace", "delete_file", "web_fetch"}
