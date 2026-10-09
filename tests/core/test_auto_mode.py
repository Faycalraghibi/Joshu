"""Auto mode: edits run, other actions that would ask are reviewed by a model."""

import os
import sys

import pytest
from test_agent_loop import FakeClient, call, make_agent, text, tool_messages

from joshu.core.auto_mode import Review, parse_review, review_action
from joshu.core.permissions import ApprovalChoice, PermissionManager, PermissionMode
from joshu.tools import filesystem_tools


@pytest.fixture
def workspace(tmp_path):
    filesystem_tools.set_workspace_root(tmp_path)
    yield tmp_path
    filesystem_tools._workspace_root = None


def manager(review, approver=None):
    permissions = PermissionManager(PermissionMode.AUTO, approver=approver)
    permissions.reviewer = lambda tool, arguments: review
    return permissions


ECHO = {"command": "python -m pytest -q"}


def test_allowed_actions_run_without_asking():
    assert manager(Review(True, "runs the tests")).check("run_shell_command", ECHO, True).allowed


def test_blocked_actions_ask_or_are_refused():
    asked = []

    def approver(request):
        asked.append(request.warning)
        return ApprovalChoice.YES

    blocked = Review(False, "pushes to the remote")
    decision = manager(blocked).check("run_shell_command", {"command": "git push"}, True)
    assert (
        not decision.allowed and "Auto mode blocked this: pushes to the remote" in decision.reason
    )
    assert (
        manager(blocked, approver).check("run_shell_command", {"command": "git push"}, True).allowed
    )
    assert asked == ["Auto mode: pushes to the remote"]
    # no answer from the review: never runs unasked
    assert not manager(None).check("run_shell_command", ECHO, True).allowed


def test_edits_run_without_a_review_and_secrets_still_ask():
    reviews = []
    permissions = PermissionManager(PermissionMode.AUTO)
    permissions.reviewer = lambda tool, arguments: reviews.append(tool) or Review(True, "")
    assert permissions.check("write_file", {"path": "a.py", "content": "x"}, True).allowed
    assert not permissions.check("read_file", {"path": ".env"}, False).allowed
    assert reviews == []


def test_unsafe_commands_still_ask():
    dangerous = "format C:" if os.name == "nt" else "rm -rf /"
    decision = manager(Review(True, "fine")).check(
        "run_shell_command", {"command": dangerous}, True
    )
    assert not decision.allowed


@pytest.mark.parametrize(
    "answer, expected",
    [
        ('{"decision": "allow", "reason": "runs the tests"}', Review(True, "runs the tests")),
        (
            'Sure.\n```json\n{"decision": "BLOCK", "reason": "deletes ~"}\n```',
            Review(False, "deletes ~"),
        ),
        ("I think it's fine", None),
        ('{"decision": "maybe"}', None),
    ],
)
def test_parse_review(answer, expected):
    assert parse_review(answer) == expected


def test_review_sends_the_request_and_the_action():
    client = FakeClient([text('{"decision": "allow", "reason": "ok"}')])
    review = review_action(client, "fix the tests", "run_shell_command", ECHO, "/repo")
    assert review == Review(True, "ok")
    sent = client.requests[0][1]["content"]
    assert "fix the tests" in sent and "python -m pytest -q" in sent and "/repo" in sent


def test_the_agent_reviews_with_its_model(workspace):
    command = f'"{sys.executable}" -c "print(42)"'
    client = FakeClient(
        [
            call("run_shell_command", command=command),
            text('{"decision": "allow", "reason": "a local script"}'),  # the review
            text("It printed 42."),
        ]
    )
    agent = make_agent(client, mode=PermissionMode.AUTO)
    assert agent.run("run the script").text == "It printed 42."
    assert '"exit_code": 0' in tool_messages(agent.messages)[0]["content"]
    assert "run the script" in client.requests[1][1]["content"]  # the review saw the request
