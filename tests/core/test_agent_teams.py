"""Agent teams: teammates that work at the same time, message each other, share tasks."""

import threading
import time

import pytest
from test_agent_loop import call, make_agent, text
from test_worktree_subagents import git

from joshu.core.llm_client import AssistantTurn, ToolCall
from joshu.core.permissions import PermissionMode
from joshu.core.team import LEAD, Member, Team, wait_idle
from joshu.tools import filesystem_tools


@pytest.fixture
def workspace(tmp_path):
    filesystem_tools.set_workspace_root(tmp_path)
    yield tmp_path
    filesystem_tools._workspace_root = None


def spawn(call_id="sp", **arguments):
    """call() can't take a `name` argument (its own first parameter)."""
    import json

    return AssistantTurn(
        tool_calls=[ToolCall(id=call_id, name="spawn_teammate", arguments=json.dumps(arguments))]
    )


# ---------------------------------------------------------------- the team


def test_a_run_reports_to_the_lead_and_a_message_wakes_an_idle_teammate():
    prompts = []
    team = Team(lambda member, prompt: prompts.append(prompt) or f"answer {len(prompts)}")
    team.add(Member("scout", "looks around"), "first task")
    assert wait_idle(team, 5)
    assert team.take(LEAD) == ["[Teammate scout finished a run]\nanswer 1"]
    assert team.send(LEAD, "scout", "look at x") == "Sent to scout. Woke up: scout."
    assert wait_idle(team, 5)
    assert prompts == ["first task", "[Message from lead]\nlook at x"]
    assert "Error: no teammate 'nobody'" in team.send(LEAD, "nobody", "hi")


def test_messages_to_a_working_teammate_wait_for_its_next_turn():
    gate = threading.Event()
    prompts = []

    def runner(member, prompt):
        prompts.append(prompt)
        if len(prompts) == 1:
            gate.wait(5)
        return "ok"

    team = Team(runner)
    team.add(Member("dev", "codes"), "start")
    time.sleep(0.1)
    team.send(LEAD, "dev", "also do y")  # it's working: queued
    assert team.members["dev"].inbox == ["[Message from lead]\nalso do y"]
    gate.set()
    assert wait_idle(team, 5)
    # it had ended its run with the message unread: it goes on with it
    assert prompts == ["start", "[Message from lead]\nalso do y"]


def test_the_shared_task_list():
    team = Team(lambda member, prompt: "")
    assert team.task_action("lead", "add", "write the parser") == "Added task 1: write the parser"
    assert "claimed (dev)" in team.task_action("dev", "claim", task_id=1)
    assert "Error: task 1 is claimed by dev" in team.task_action("qa", "claim", task_id=1)
    assert "done (dev)" in team.task_action("dev", "done", task_id=1, note="in parse.py")
    listing = team.task_action("qa", "list")
    assert "1. [done] [dev] write the parser (in parse.py)" in listing


# ------------------------------------------------------------- with agents


class Router:
    """The lead's turns, and each teammate's (found by its name in its first message)."""

    model = "fake-model"

    def __init__(self, lead, members):
        self.lead = list(lead)
        self.members = {name: list(turns) for name, turns in members.items()}
        self.lock = threading.Lock()
        self.offered = {}
        self.lead_requests = []

    def complete(self, messages, tools=None, **kwargs):
        first = next((m["content"] for m in messages if m["role"] == "user"), "")
        with self.lock:
            for name, turns in self.members.items():
                if f"You are {name}," in str(first):
                    self.offered[name] = {t["function"]["name"] for t in tools or []}
                    return turns.pop(0)
            self.lead_requests.append([dict(m) for m in messages])
            return self.lead.pop(0)


def test_the_lead_spawns_a_teammate_and_hears_from_it(workspace):
    client = Router(
        lead=[
            spawn(name="scout", role="finds things", instructions="find x"),
            call("team_tasks", "c2", action="wait", timeout=10),
            text("Scout found it."),
        ],
        members={
            "scout": [
                call("send_message", "s1", to="lead", message="x is in y.py"),
                text("Done: x is in y.py."),
            ]
        },
    )
    agent = make_agent(client)
    assert agent.run("find x with a teammate").text == "Scout found it."
    # between its turns or as the wait's result, whichever came first
    heard = "\n".join(str(m.get("content")) for m in agent.messages[1:])
    assert "[Message from scout]\nx is in y.py" in heard
    assert "[Teammate scout finished a run]\nDone: x is in y.py." in heard
    wait_idle(agent.team, 5)
    # a read-only teammate: team tools, no edits, can't start its own team
    offered = client.offered["scout"]
    assert {"send_message", "team_tasks", "read_file"} <= offered
    assert not offered & {"write_file", "run_shell_command", "spawn_teammate"}
    assert "spawn_teammate" in {t["function"]["name"] for t in agent.request_tools()}


def test_names_and_limits(workspace):
    client = Router(lead=[], members={})
    agent = make_agent(client, cwd=workspace)  # not a git repository
    spawn = agent._local_tools["spawn_teammate"].function
    assert "Error: name" in spawn(name="Lead", role="r", instructions="i")
    assert "git repository" in spawn(name="dev", role="r", instructions="i", edit=True)


def test_an_editing_teammate_works_in_a_worktree(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    git(root, "init", "-q")
    (root / "a.py").write_text("A = 1\n", encoding="utf-8")
    git(root, "add", ".")
    git(root, "commit", "-qm", "init")
    filesystem_tools.set_workspace_root(root)
    try:
        client = Router(
            lead=[
                spawn(name="dev", role="codes", instructions="set A to 2", edit=True),
                call("team_tasks", "c2", action="wait", timeout=15),
                text("Done."),
            ],
            members={
                "dev": [
                    call("replace", "r1", path="a.py", old_string="A = 1", new_string="A = 2"),
                    text("Set A to 2."),
                ]
            },
        )
        agent = make_agent(client, mode=PermissionMode.ACCEPT_EDITS, cwd=root)
        agent.run("change A with a teammate")
        assert wait_idle(agent.team, 15)
        assert (root / "a.py").read_text(encoding="utf-8") == "A = 2\n"
        assert "Applied to the working tree" in agent.team.members["dev"].last
    finally:
        filesystem_tools._workspace_root = None


def test_the_team_command(tmp_path, monkeypatch):
    from unittest.mock import MagicMock, patch

    pytest.importorskip("prompt_toolkit")
    monkeypatch.chdir(tmp_path)
    from joshu.ui.interactive import InteractiveMode

    with patch("joshu.ui.interactive.interactive_mode.ContextProvider"):
        mode = InteractiveMode("test-model", sandbox=False, verbose=False)
    prompts = []
    team = Team(lambda member, prompt: prompts.append(prompt) or "ok")
    team.add(Member("dev", "codes"), "start")
    wait_idle(team, 5)
    mode.agent = MagicMock(team=team)
    printed = []
    with patch("joshu.ui.interactive.commands_more._console") as console:
        console.return_value.print.side_effect = lambda *a, **k: printed.append(str(a[0]))
        mode.command_handler.handle_slash_command("/team")
        mode.command_handler.handle_slash_command("/team dev please add tests")
    assert "dev (idle, 1 run(s)): codes" in printed[0]
    assert printed[1] == "Sent to dev. Woke up: dev."
    wait_idle(team, 5)
    assert prompts[-1] == "[Message from user]\nplease add tests"
