"""exit_plan_mode: the agent shows its plan, the user approves it, and it carries it out."""

import pytest
from test_agent_loop import (
    FakeClient,
    RecordingEvents,
    call,
    make_agent,
    text,
    tool_messages,
)

from joshu.core.agent import PLAN_ACCEPT_EDITS, PLAN_ASK_EDITS, PLAN_KEEP
from joshu.core.permissions import PermissionMode
from joshu.tools import filesystem_tools


@pytest.fixture
def workspace(tmp_path):
    filesystem_tools.set_workspace_root(tmp_path)
    yield tmp_path
    filesystem_tools._workspace_root = None


class Answering(RecordingEvents):
    can_ask_user = True

    def __init__(self, answer):
        super().__init__()
        self.answer = answer
        self.plans = []
        self.asked = []

    def show_plan(self, plan):
        self.plans.append(plan)

    def ask_user(self, questions):
        self.asked.append(questions)
        return [self.answer]


def offered(tools):
    return {t["function"]["name"] for t in tools or []}


def test_approved_plan_is_carried_out_in_the_same_request(workspace):
    events = Answering([PLAN_ACCEPT_EDITS])
    client = FakeClient(
        [
            call("exit_plan_mode", plan="1. Create notes.txt"),
            call("write_file", "c2", path="notes.txt", content="hi"),
            text("Done."),
        ]
    )
    agent = make_agent(client, mode=PermissionMode.PLAN, events=events)
    assert agent.run("plan then do it").text == "Done."
    assert events.plans == ["1. Create notes.txt"]
    assert [label for label, _ in events.asked[0][0].options] == [
        PLAN_ACCEPT_EDITS,
        PLAN_ASK_EDITS,
        PLAN_KEEP,
    ]
    assert agent.permissions.mode == PermissionMode.ACCEPT_EDITS
    assert (workspace / "notes.txt").read_text(encoding="utf-8") == "hi"
    assert "approved the plan" in tool_messages(agent.messages)[0]["content"]
    # the tool isn't offered any more, and the generated prompt has left plan mode
    assert "exit_plan_mode" not in offered(client.tools_offered[1])
    agent._system_prompt_override = None
    assert "PLAN mode" not in agent._build_system_prompt()


def test_feedback_keeps_planning(workspace):
    events = Answering("use b.py instead")
    client = FakeClient([call("exit_plan_mode", plan="edit a.py"), text("Revised.")])
    agent = make_agent(client, mode=PermissionMode.PLAN, events=events)
    agent.run("plan it")
    result = tool_messages(agent.messages)[0]["content"]
    assert "didn't approve" in result and "use b.py instead" in result
    assert agent.permissions.mode == PermissionMode.PLAN


def test_offered_only_in_plan_mode_with_someone_to_ask(workspace):
    client = FakeClient([text("ok")])
    agent = make_agent(client, mode=PermissionMode.PLAN, events=Answering(None))
    agent.run("x")
    assert "exit_plan_mode" in offered(client.tools_offered[0])
    agent._system_prompt_override = None
    assert "call exit_plan_mode" in agent._build_system_prompt()  # told when to call it

    client = FakeClient([text("ok")])
    make_agent(client, mode=PermissionMode.DEFAULT, events=Answering(None)).run("x")
    assert "exit_plan_mode" not in offered(client.tools_offered[0])

    client = FakeClient([text("ok")])
    make_agent(client, mode=PermissionMode.PLAN).run("x")  # headless: no one to approve
    assert "exit_plan_mode" not in offered(client.tools_offered[0])
