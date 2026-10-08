"""Running the project's tests before finishing a request that edited code."""

import json
import sys

import pytest
from test_agent_loop import FakeClient, call, make_agent, text

from joshu.core import verify
from joshu.core.config import get_config_manager
from joshu.core.permissions import PermissionMode
from joshu.tools import filesystem_tools

PYTEST = f'"{sys.executable}" -m pytest -q -x -p no:cacheprovider'


@pytest.fixture
def project(tmp_path):
    root = tmp_path / "project"
    root.mkdir()
    (root / "calc.py").write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")
    (root / "test_calc.py").write_text(
        "from calc import add\n\n\ndef test_add():\n    assert add(2, 3) == 5\n", encoding="utf-8"
    )
    filesystem_tools.set_workspace_root(root)
    get_config_manager().set("verify_command", PYTEST)
    yield root
    filesystem_tools._workspace_root = None


def edit(old, new, call_id="e1"):
    return call("replace", call_id=call_id, path="calc.py", old_string=old, new_string=new)


def notes(client):
    return [
        m["content"]
        for request in client.requests
        for m in request
        if m.get("role") == "user" and str(m.get("content", "")).startswith("[Verification]")
    ]


def test_failing_tests_go_back_to_the_model(project):
    client = FakeClient(
        [
            edit("return a + b", "return a - b"),
            text("Done."),
            edit("return a - b", "return a + b", "e2"),
            text("Fixed it."),
        ]
    )
    response = make_agent(client, mode=PermissionMode.BYPASS, cwd=project).run("change add")
    assert response.text == "Fixed it." and response.metadata["verification"] == "passed"
    (note,) = set(notes(client))
    assert "fail" in note and "assert" in note and PYTEST in note


def test_passing_tests_finish_without_an_extra_turn(project):
    client = FakeClient([edit("return a + b", "return b + a"), text("Done.")])
    response = make_agent(client, mode=PermissionMode.BYPASS, cwd=project).run("swap")
    assert response.text == "Done." and len(client.requests) == 2
    assert response.metadata["verification"] == "passed"


def test_not_run_again_when_the_agent_ran_the_tests(project):
    client = FakeClient(
        [
            edit("return a + b", "return b + a"),
            call("run_shell_command", call_id="t1", command=PYTEST),
            text("Done, tests pass."),
        ]
    )
    response = make_agent(client, mode=PermissionMode.BYPASS, cwd=project).run("swap")
    assert response.metadata["verification"] is None


def test_gives_up_after_two_rounds(project):
    # The model never fixes it: checked again each time it tries to finish, twice
    client = FakeClient([edit("return a + b", "return 0"), text("one"), text("two"), text("three")])
    response = make_agent(client, mode=PermissionMode.BYPASS, cwd=project).run("break it")
    assert response.text == "three" and len(notes(client)) >= 2
    assert response.metadata["verification"] == "failed"


def test_needs_permission(project):
    # Default mode without anyone to ask: the command isn't run
    client = FakeClient([edit("return a + b", "return a - b"), text("Done.")])
    agent = make_agent(client, mode=PermissionMode.ACCEPT_EDITS, cwd=project)
    assert agent.run("change").text == "Done."
    assert notes(client) == []


def test_missing_runner_turns_it_off(project):
    get_config_manager().set("verify_command", "definitely-not-a-command-xyz --run")
    client = FakeClient([edit("return a + b", "return a - b"), text("Done.")])
    agent = make_agent(client, mode=PermissionMode.BYPASS, cwd=project)
    assert agent.run("change").text == "Done." and agent._verify_off


def test_detect_command(tmp_path):
    def project(files):
        root = tmp_path / str(len(list(tmp_path.iterdir())))
        root.mkdir()
        for name, content in files.items():
            (root / name).parent.mkdir(parents=True, exist_ok=True)
            (root / name).write_text(content, encoding="utf-8")
        return verify.detect_command(root)

    assert (
        project({"package.json": json.dumps({"scripts": {"test": "jest"}})}) == "npm test --silent"
    )
    default = 'echo "Error: no test specified" && exit 1'
    assert project({"package.json": json.dumps({"scripts": {"test": default}})}) is None
    assert project({"go.mod": "module x"}) == "go test ./..."
    assert project({"Cargo.toml": "[package]"}) == "cargo test -q"
    assert "-m pytest" in project({"tests/test_x.py": ""})
    assert "-m pytest" in project({"pyproject.toml": "[tool.pytest.ini_options]\n"})
    assert "-m pytest" in project({"conftest.py": ""})
    assert project({"app.py": "x = 1"}) is None


def test_settings_and_helpers(tmp_path):
    config = get_config_manager()
    config.set("verify_command", "off")
    assert verify.configured_command(tmp_path) is None
    config.set("verify_command", "make check")
    assert verify.configured_command(tmp_path) == "make check"
    assert verify.runs_tests("python -m pytest -q") and verify.runs_tests("python test_parse.py")
    assert not verify.runs_tests("python app.py")
    assert verify.runner_missing("/usr/bin/python: No module named pytest")
    assert "[... earlier output omitted]" in verify.failure_note("t", 1, "x" * 5000)
