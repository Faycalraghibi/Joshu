"""The trace: timing of every model call and tool run, saved with the session."""

import json

from test_agent_loop import FakeClient, call, make_agent, text
from typer.testing import CliRunner

from joshu.core.llm_client import AssistantTurn
from joshu.core.permissions import PermissionMode
from joshu.core.sessions import load_session
from joshu.core.trace import render, summary
from joshu.tools import filesystem_tools


def test_model_calls_and_tools_are_traced(tmp_path):
    filesystem_tools.set_workspace_root(tmp_path)
    try:
        (tmp_path / "a.py").write_text("x = 1\n", encoding="utf-8")
        turn = call("read_file", path="a.py")
        turn.usage = {"prompt_tokens": 1200, "completion_tokens": 30}
        client = FakeClient([turn, call("read_file", call_id="c2", path="nope.py"), text("done")])
        agent = make_agent(client, mode=PermissionMode.BYPASS, cwd=tmp_path, persist=True)
        agent.run("look")
    finally:
        filesystem_tools._workspace_root = None

    kinds = [(e["kind"], e["name"]) for e in agent.trace]
    assert kinds == [
        ("model", "fake-model"),
        ("tool", "read_file"),
        ("model", "fake-model"),
        ("tool", "read_file"),
        ("model", "fake-model"),
    ]
    first = agent.trace[0]
    assert first["prompt_tokens"] == 1200 and first["tool_calls"] == 1 and first["thinking"] is True
    assert first["request"] == 1 and first["seconds"] >= 0 and "T" in first["at"]
    assert agent.trace[1]["success"] is True and agent.trace[3]["success"] is False

    # Saved with the session, and back after a resume
    saved = load_session(agent.session_id)
    assert saved["trace"] == agent.trace
    again = make_agent(FakeClient([]), cwd=tmp_path)
    again.restore(saved)
    assert again.trace == agent.trace


def test_summary_and_render():
    trace = [
        {"kind": "model", "name": "m", "seconds": 40, "thinking": True, "request": 1},
        {"kind": "tool", "name": "read_file", "seconds": 0.1, "success": True, "request": 1},
        {"kind": "model", "name": "m", "seconds": 4, "thinking": False, "request": 1},
        {
            "kind": "tool",
            "name": "run_shell_command",
            "seconds": 12,
            "success": False,
            "request": 1,
        },
    ]
    totals = summary(trace)
    assert totals["model_calls"] == 2 and totals["seconds_per_call"] == 22.0
    assert (
        totals["seconds_per_call_thinking"] == 40 and totals["seconds_per_call_not_thinking"] == 4
    )
    assert totals["failed_tool_runs"] == 1 and totals["slowest_tools"][0][0] == "run_shell_command"
    text_out = render(trace)
    assert (
        "no thinking" in text_out and "2 model calls, 44.0s" in text_out and "1 failed" in text_out
    )


def test_trace_command(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    client = FakeClient([AssistantTurn(content="hi", usage={"prompt_tokens": 10})])
    agent = make_agent(client, cwd=tmp_path, persist=True)
    agent.run("hello")
    from joshu.ui.cli import app

    result = CliRunner().invoke(app, ["trace", agent.session_id[:8]])
    assert result.exit_code == 0 and "model" in result.output and "1 model calls" in result.output
    lines = CliRunner().invoke(app, ["trace", "--json"]).output.strip().splitlines()
    assert json.loads(lines[0])["kind"] == "model"
    assert CliRunner().invoke(app, ["trace", "nope"]).exit_code == 1
