"""Sub-agents that edit in their own git worktree; their work is applied when they finish."""

import json
import subprocess
import sys
import threading

import pytest
from test_agent_loop import call, make_agent, text, tool_messages

from joshu.core import worktrees
from joshu.core.llm_client import AssistantTurn, ToolCall
from joshu.core.permissions import PermissionMode
from joshu.tools import filesystem_tools


def git(cwd, *args):
    return subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", *args],
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
    ).stdout


@pytest.fixture
def repo(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    git(root, "init", "-q")
    (root / "a.py").write_text("A = 1\n", encoding="utf-8")
    (root / "b.py").write_text("B = 1\n", encoding="utf-8")
    git(root, "add", ".")
    git(root, "commit", "-qm", "init")
    filesystem_tools.set_workspace_root(root)
    yield root
    filesystem_tools._workspace_root = None


class ScriptedByPrompt:
    """Answers each conversation from the script for the keyword in its first request."""

    model = "fake-model"

    def __init__(self, scripts):
        self.scripts = {key: list(turns) for key, turns in scripts.items()}
        self.lock = threading.Lock()
        self.tools_offered = []
        self.seen = {}

    def complete(self, messages, tools=None, **kwargs):
        first = next(m["content"] for m in messages if m["role"] == "user")
        with self.lock:
            self.tools_offered.append({t["function"]["name"]: t for t in tools or []})
            for key, turns in self.scripts.items():
                if key in first:
                    self.seen[key] = [dict(m) for m in messages]
                    return turns.pop(0)
        raise AssertionError(f"no script for {first!r}")


def edit_task(call_id, key, description="change a"):
    return call("task", call_id=call_id, description=description, prompt=f"{key}: do it", edit=True)


def replace(path, old, new, call_id="r1"):
    return call("replace", call_id=call_id, path=path, old_string=old, new_string=new)


def test_work_is_applied_to_the_working_tree(repo):
    client = ScriptedByPrompt(
        {
            "MAIN": [edit_task("t1", "SUB"), text("All done.")],
            "SUB": [replace("a.py", "A = 1", "A = 2"), text("Set A to 2.")],
        }
    )
    agent = make_agent(client, mode=PermissionMode.BYPASS, cwd=repo)
    assert agent.run("MAIN request").text == "All done."
    result = tool_messages(agent.messages)[0]["content"]
    assert "Set A to 2." in result and "Applied to the working tree" in result
    assert (repo / "a.py").read_text(encoding="utf-8") == "A = 2\n"
    assert "joshu/" not in git(repo, "branch")  # branch removed once applied
    assert list(worktrees.worktrees_dir().glob("*")) == []
    assert git(repo, "status", "--porcelain").strip() == "M a.py"  # not staged, not committed
    # The edit is in the request's checkpoint: it can be undone
    agent.undo()
    assert (repo / "a.py").read_text(encoding="utf-8") == "A = 1\n"


def test_sub_agent_sees_uncommitted_work(repo):
    (repo / "a.py").write_text("A = 'uncommitted'\n", encoding="utf-8")
    (repo / "new.py").write_text("NEW = 1\n", encoding="utf-8")  # untracked
    client = ScriptedByPrompt(
        {
            "MAIN": [edit_task("t1", "SUB", "change b"), text("ok")],
            "SUB": [
                call("read_file", call_id="r0", path="a.py"),
                call("read_file", call_id="r1", path="new.py"),
                replace("b.py", "B = 1", "B = 2"),
                text("done"),
            ],
        }
    )
    agent = make_agent(client, mode=PermissionMode.BYPASS, cwd=repo)
    agent.run("MAIN request")
    reads = [m["content"] for m in tool_messages(client.seen["SUB"])]
    assert "uncommitted" in reads[0] and "NEW = 1" in reads[1]
    # Only the sub-agent's own change comes back; the uncommitted work is untouched
    assert (repo / "b.py").read_text(encoding="utf-8") == "B = 2\n"
    assert (repo / "a.py").read_text(encoding="utf-8") == "A = 'uncommitted'\n"
    assert (repo / "new.py").read_text(encoding="utf-8") == "NEW = 1\n"
    assert "Applied" in tool_messages(agent.messages)[0]["content"]


def test_applies_over_uncommitted_changes_to_the_same_file(repo):
    (repo / "a.py").write_text("A = 1\nOTHER = 1\n", encoding="utf-8")
    client = ScriptedByPrompt(
        {
            "MAIN": [edit_task("t1", "SUB"), text("ok")],
            "SUB": [replace("a.py", "A = 1", "A = 2"), text("done")],
        }
    )
    agent = make_agent(client, mode=PermissionMode.BYPASS, cwd=repo)
    agent.run("MAIN request")
    assert (repo / "a.py").read_text(encoding="utf-8") == "A = 2\nOTHER = 1\n"
    assert "joshu/" not in git(repo, "branch")


def test_changes_made_meanwhile_keep_the_work_on_a_branch(repo):
    main_file = (repo / "a.py").resolve()
    # While the sub-agent works, the same line changes in the working tree
    meanwhile = f"\"{sys.executable}\" -c \"open(r'{main_file}', 'w').write('A = 99')\""
    client = ScriptedByPrompt(
        {
            "MAIN": [edit_task("t1", "SUB"), text("ok")],
            "SUB": [
                call("run_shell_command", call_id="s0", command=meanwhile),
                replace("a.py", "A = 1", "A = 2"),
                text("done"),
            ],
        }
    )
    agent = make_agent(client, mode=PermissionMode.BYPASS, cwd=repo)
    agent.run("MAIN request")
    result = tool_messages(agent.messages)[0]["content"]
    assert "Not applied" in result
    branch = next(line.strip() for line in git(repo, "branch").splitlines() if "joshu/" in line)
    assert (repo / "a.py").read_text(encoding="utf-8") == "A = 99"
    assert "A = 2" in git(repo, "show", f"{branch}:a.py")


def test_no_changes(repo):
    client = ScriptedByPrompt(
        {"MAIN": [edit_task("t1", "SUB"), text("ok")], "SUB": [text("Nothing to change.")]}
    )
    agent = make_agent(client, mode=PermissionMode.BYPASS, cwd=repo)
    agent.run("MAIN request")
    assert "changed no files" in tool_messages(agent.messages)[0]["content"]
    assert "joshu/" not in git(repo, "branch")


def test_parallel_edit_tasks(repo):
    first = AssistantTurn(
        tool_calls=[
            ToolCall(
                id=f"t{i}",
                name="task",
                arguments=json.dumps(
                    {"description": f"change {k}", "prompt": f"SUB{k}: go", "edit": True}
                ),
            )
            for i, k in enumerate("ab")
        ]
    )
    client = ScriptedByPrompt(
        {
            "MAIN": [first, text("both done")],
            "SUBa": [replace("a.py", "A = 1", "A = 2"), text("a done")],
            "SUBb": [replace("b.py", "B = 1", "B = 2"), text("b done")],
        }
    )
    agent = make_agent(client, mode=PermissionMode.BYPASS, cwd=repo)
    assert agent.run("MAIN request").text == "both done"
    assert (repo / "a.py").read_text(encoding="utf-8") == "A = 2\n"
    assert (repo / "b.py").read_text(encoding="utf-8") == "B = 2\n"


def test_offered_only_in_a_repository_and_not_in_plan_mode(repo, tmp_path):
    client = ScriptedByPrompt({"MAIN": [text("hi")]})
    make_agent(client, mode=PermissionMode.BYPASS, cwd=repo).run("MAIN request")
    assert "edit" in client.tools_offered[0]["task"]["function"]["parameters"]["properties"]

    plain = tmp_path / "plain"
    plain.mkdir()
    client = ScriptedByPrompt({"MAIN": [text("hi")]})
    make_agent(client, mode=PermissionMode.BYPASS, cwd=plain).run("MAIN request")
    assert "edit" not in client.tools_offered[0]["task"]["function"]["parameters"]["properties"]

    client = ScriptedByPrompt({"MAIN": [edit_task("t1", "SUB"), text("ok")]})
    agent = make_agent(client, mode=PermissionMode.PLAN, cwd=repo)
    agent.run("MAIN request")
    assert "plan mode" in tool_messages(agent.messages)[0]["content"]


def test_workspace_context(tmp_path):
    from joshu.tools.filesystem_tools import context_root, resolve_path, workspace
    from joshu.tools.shell_tool import _default_cwd

    other = tmp_path / "wt"
    other.mkdir()
    assert context_root() is None and _default_cwd(None) is None
    with workspace(other):
        assert resolve_path("x.py") == other.resolve() / "x.py"
        assert _default_cwd(None) == str(other.resolve())
        assert _default_cwd("sub") == str(other.resolve() / "sub")
    assert context_root() is None
