"""Clearing old tool results, and read_file's whole-line limit for large files."""

import json

import pytest
from test_agent_loop import (
    FakeClient,
    RecordingEvents,
    call,
    make_agent,
    text,
    tool_messages,
)

from joshu.core import context_editing
from joshu.core.context_editing import (
    CLEARED_PREFIX,
    clear_old_tool_results,
    describe_call,
)
from joshu.core.permissions import PermissionMode
from joshu.tools import filesystem_tools
from joshu.tools.filesystem_tools import READ_MAX_CHARS, read_file_tool


@pytest.fixture
def workspace(tmp_path):
    filesystem_tools.set_workspace_root(tmp_path)
    yield tmp_path
    filesystem_tools._workspace_root = None


def conversation(results, names=None):
    """System prompt, a request, then one tool call + result per entry."""
    messages = [{"role": "system", "content": "s"}, {"role": "user", "content": "go"}]
    for i, content in enumerate(results):
        name = (names or {}).get(i, "read_file")
        messages.append(
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {
                        "id": f"c{i}",
                        "type": "function",
                        "function": {"name": name, "arguments": json.dumps({"path": f"f{i}.py"})},
                    }
                ],
            }
        )
        messages.append({"role": "tool", "tool_call_id": f"c{i}", "content": content})
    return messages


BIG = "x" * 4000  # ~1k tokens each


def test_old_results_are_cleared_recent_ones_kept():
    messages = conversation([BIG] * 30)
    cleared, count, freed = clear_old_tool_results(messages, keep_recent=6)

    results = [m["content"] for m in cleared if m.get("role") == "tool"]
    assert count == 24 and freed > 20000
    assert all(r.startswith(CLEARED_PREFIX) for r in results[:24])
    assert results[24:] == [BIG] * 6
    assert "read_file(path=f0.py)" in results[0]
    assert messages[3]["content"] == BIG  # input untouched


def test_nothing_happens_when_too_little_would_be_freed():
    messages = conversation([BIG] * 8)
    assert clear_old_tool_results(messages, keep_recent=6) == (messages, 0, 0)


def test_skills_subagents_and_small_results_are_kept():
    results = [BIG] * 30
    results[0] = "short"
    names = {1: "skill", 2: "task"}
    cleared, _, _ = clear_old_tool_results(conversation(results, names), keep_recent=6)
    tool_results = [m["content"] for m in cleared if m.get("role") == "tool"]
    assert tool_results[:3] == ["short", BIG, BIG]
    assert tool_results[3].startswith(CLEARED_PREFIX)


def test_old_write_file_contents_are_cleared():
    messages = conversation([BIG] * 30)
    messages[2]["tool_calls"][0]["function"] = {
        "name": "write_file",
        "arguments": json.dumps({"path": "new.py", "content": "y" * 5000}),
    }
    cleared, _, _ = clear_old_tool_results(messages, keep_recent=6)
    arguments = json.loads(cleared[2]["tool_calls"][0]["function"]["arguments"])
    assert arguments["path"] == "new.py"
    assert arguments["content"] == f"{CLEARED_PREFIX}: 5000 characters written]"


def test_cleared_results_are_not_cleared_twice():
    first, count, _ = clear_old_tool_results(conversation([BIG] * 30), keep_recent=6)
    again, count_again, _ = clear_old_tool_results(first, keep_recent=6)
    assert count and count_again == 0 and again is first


def test_describe_call_is_short():
    assert describe_call("run_shell_command", {"command": "pytest " + "-q " * 50}).endswith("...)")
    assert describe_call("", {}) == "a tool call"


# ------------------------------------------------------------------ the agent


def test_agent_clears_when_context_grows(workspace, monkeypatch):
    from joshu.core.config import get_config_manager

    monkeypatch.setattr(context_editing, "MIN_FREED_TOKENS", 1000)
    for i in range(12):
        (workspace / f"f{i}.py").write_text(f"# file {i}\n" + "x = 1\n" * 700, encoding="utf-8")
    get_config_manager().set("clear_tool_results_at", 6000)
    try:
        turns = [call("read_file", call_id=f"c{i}", path=f"f{i}.py") for i in range(12)]
        events = RecordingEvents()
        cleared = []
        events.on_context_cleared = lambda items, freed: cleared.append((items, freed))
        agent = make_agent(
            FakeClient(turns + [text("done")]), mode=PermissionMode.PLAN, events=events
        )
        agent.run("read them all")
    finally:
        get_config_manager().set("clear_tool_results_at", 60000)

    assert cleared and cleared[0][0] > 0
    contents = [m["content"] for m in tool_messages(agent.messages)]
    assert contents[0].startswith(CLEARED_PREFIX)
    assert "file 11" in contents[-1]


def test_clearing_threshold_is_capped_at_half_the_window(workspace):
    agent = make_agent(FakeClient([]), context_window=32000)
    assert agent.clear_tool_results_at == 16000


# ----------------------------------------------------------------- read_file


def test_large_files_return_whole_lines_and_how_to_continue(workspace):
    line = "value = 'some text here'\n"
    (workspace / "big.py").write_text(line * 4000, encoding="utf-8")
    result = read_file_tool("big.py")
    assert result["success"] and result["total_lines"] == 4000
    assert len(result["content"]) <= READ_MAX_CHARS
    assert result["content"].endswith("'some text here'")  # cut at a line boundary
    shown = result["end_line"]
    assert f"start_line={shown + 1}" in result["note"]

    part = read_file_tool("big.py", start_line=shown + 1, end_line=shown + 10)
    assert part["start_line"] == shown + 1 and "note" not in part


def test_small_files_are_returned_whole(workspace):
    (workspace / "small.py").write_text("a = 1\n", encoding="utf-8")
    result = read_file_tool("small.py")
    assert result["content"] == "a = 1\n" and "note" not in result
