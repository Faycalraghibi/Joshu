"""task(background=true): a sub-agent works while the main agent goes on."""

import json
import re
import threading
import time

import pytest
from test_agent_loop import call, make_agent, text

from joshu.tools import filesystem_tools


@pytest.fixture
def workspace(tmp_path):
    filesystem_tools.set_workspace_root(tmp_path)
    yield tmp_path
    filesystem_tools._workspace_root = None


class Router:
    """Scripted turns for the main agent and its sub-agents, which run at the same time."""

    model = "fake-model"

    def __init__(self, main, sub, gate=None):
        self.main, self.sub, self.gate = list(main), list(sub), gate
        self.main_requests = []

    def complete(self, messages, tools=None, **kwargs):
        if "sub-agent" in str(messages[0]["content"]):
            if self.gate is not None:
                self.gate.wait(5)
            return self.sub.pop(0)
        self.main_requests.append([dict(m) for m in messages])
        turn = self.main.pop(0)
        return turn(messages) if callable(turn) else turn


def started_id(messages):
    last = [m for m in messages if m.get("role") == "tool"][-1]["content"]
    return re.search(r"background task (\w+)", last).group(1)


def wait_done(agent):
    deadline = time.time() + 5
    while agent.background_running() and time.time() < deadline:
        time.sleep(0.01)


def test_task_output_waits_for_the_answer(workspace):
    client = Router(
        main=[
            call("task", description="survey", prompt="survey", background=True),
            lambda m: call("task_output", "c2", task_id=started_id(m), wait=True),
            text("Done."),
        ],
        sub=[text("auth lives in auth.py")],
    )
    agent = make_agent(client)
    agent.run("survey in the background")
    last_tool = [m for m in agent.messages if m.get("role") == "tool"][-1]["content"]
    assert "finished" in last_tool and "auth lives in auth.py" in last_tool
    # read with task_output: not delivered a second time
    assert agent._finished_background_tasks() == []


def test_a_finished_answer_arrives_between_turns(workspace):
    (workspace / "a.txt").write_text("a", encoding="utf-8")
    agent = None

    def after_it_finished(messages):
        wait_done(agent)
        return call("read_file", "c2", path="a.txt")

    def check(messages):
        notes = [
            m["content"]
            for m in messages
            if m.get("role") == "user" and "[Background task" in str(m["content"])
        ]
        assert len(notes) == 1 and "found it" in notes[0]
        return text("Done.")

    client = Router(
        main=[
            call("task", description="look", prompt="look", background=True),
            after_it_finished,
            check,
        ],
        sub=[text("found it")],
    )
    agent = make_agent(client)
    assert agent.run("go").text == "Done."


def test_still_running_is_told_once_and_delivered_with_the_next_message(workspace):
    gate = threading.Event()
    client = Router(
        main=[
            call("task", description="slow survey", prompt="survey", background=True),
            text("All done."),
            text("Done, the survey will follow."),
            text("Here is the survey."),
        ],
        sub=[text("survey result")],
        gate=gate,
    )
    agent = make_agent(client)
    response = agent.run("go")
    assert response.text == "Done, the survey will follow."
    told = client.main_requests[2][-1]["content"]
    assert "[Background tasks still running:" in told and "slow survey" in told
    gate.set()
    wait_done(agent)
    agent.run("and?")
    assert "survey result" in json.dumps(client.main_requests[3][-1]["content"])


def test_only_the_main_agent_starts_background_tasks(workspace):
    client = Router(main=[text("x")], sub=[])
    agent = make_agent(client)
    task = agent._local_tools["task"]
    assert "background" in task.parameters["properties"]
    assert "Error" in task.function(description="d", prompt="p", background=True, edit=True)
    sub = agent._make_subagent(agent.permissions, "x", max_turns=1)
    sub_task = sub._local_tools["task"]
    assert "background" not in sub_task.parameters["properties"]
    assert "only the main agent" in sub_task.function(description="d", prompt="p", background=True)
