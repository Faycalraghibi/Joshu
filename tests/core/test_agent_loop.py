"""End-to-end tests for the agent loop with a scripted fake model."""

import json
import os
from types import SimpleNamespace
from typing import Any, Dict, List
from unittest.mock import patch

import pytest

from joshu.core.agent import Agent, AgentEvents, truncate_output
from joshu.core.compaction import SUMMARY_PREFIX, compact_messages, find_split_index
from joshu.core.llm_client import (
    AssistantTurn,
    LLMError,
    OpenAIChatClient,
    ToolCall,
)
from joshu.core.permissions import (
    ApprovalChoice,
    PermissionManager,
    PermissionMode,
    command_key,
)
from joshu.core.tool_registry import ToolSpec
from joshu.tools import filesystem_tools


class FakeClient:
    """Returns scripted turns and records the messages it was sent."""

    model = "fake-model"

    def __init__(self, turns: List[AssistantTurn]):
        self.turns = list(turns)
        self.requests: List[List[Dict[str, Any]]] = []
        self.tools_offered: List[Any] = []

    def complete(self, messages, tools=None, *, max_tokens=4096, temperature=0.1, on_text=None):
        self.requests.append([dict(m) for m in messages])
        self.tools_offered.append(tools)
        if not self.turns:
            raise AssertionError("FakeClient ran out of scripted turns")
        turn = self.turns.pop(0)
        if on_text and turn.content:
            on_text(turn.content)
        return turn


def call(name: str, call_id: str = "call_1", **arguments) -> AssistantTurn:
    return AssistantTurn(
        tool_calls=[ToolCall(id=call_id, name=name, arguments=json.dumps(arguments))]
    )


def text(content: str) -> AssistantTurn:
    return AssistantTurn(content=content, finish_reason="stop")


class RecordingEvents(AgentEvents):
    def __init__(self):
        self.started: List[str] = []
        self.ended: List[tuple] = []
        self.text: List[str] = []

    def on_text(self, delta):
        self.text.append(delta)

    def on_tool_start(self, name, arguments):
        self.started.append(name)

    def on_tool_end(self, name, output, success):
        self.ended.append((name, success, output))


@pytest.fixture
def workspace(tmp_path):
    filesystem_tools.set_workspace_root(tmp_path)
    yield tmp_path
    filesystem_tools._workspace_root = None


def make_agent(client, mode=PermissionMode.DEFAULT, approver=None, **kwargs):
    events = kwargs.pop("events", None) or RecordingEvents()
    return Agent(
        client=client,
        permissions=PermissionManager(mode, approver=approver),
        events=events,
        system_prompt="test system prompt",
        **kwargs,
    )


def tool_messages(messages):
    return [m for m in messages if m.get("role") == "tool"]


# ----------------------------------------------------------------- the loop


def test_tool_result_is_fed_back_to_model(workspace):
    (workspace / "notes.txt").write_text("the secret is 42\n", encoding="utf-8")
    client = FakeClient([call("read_file", path="notes.txt"), text("It says 42.")])
    agent = make_agent(client)

    response = agent.run("what does notes.txt say?")

    assert response.text == "It says 42."
    assert response.metadata["turns"] == 2
    assert response.metadata["tool_calls"] == 1
    second_request = client.requests[1]
    tool_result = tool_messages(second_request)[0]
    assert tool_result["tool_call_id"] == "call_1"
    assert "the secret is 42" in tool_result["content"]
    # The assistant message carrying the tool call precedes its result
    assert second_request[-2]["tool_calls"][0]["function"]["name"] == "read_file"


def test_tools_are_offered_to_the_model(workspace):
    client = FakeClient([text("hi")])
    make_agent(client).run("hello")

    names = {tool["function"]["name"] for tool in client.tools_offered[0]}
    assert {"read_file", "replace", "run_shell_command", "glob", "task"} <= names


def test_plan_mode_denies_edits(workspace):
    target = workspace / "a.py"
    target.write_text("x = 1\n", encoding="utf-8")
    client = FakeClient(
        [call("replace", path="a.py", old_string="x = 1", new_string="x = 2"), text("ok")]
    )
    agent = make_agent(client, mode=PermissionMode.PLAN)

    agent.run("change x")

    assert target.read_text(encoding="utf-8") == "x = 1\n"
    assert "Permission denied" in tool_messages(agent.messages)[0]["content"]


def test_default_mode_without_approver_denies_edits(workspace):
    client = FakeClient([call("write_file", path="new.txt", content="hello"), text("ok")])
    agent = make_agent(client)

    agent.run("create a file")

    assert not (workspace / "new.txt").exists()
    assert "requires approval" in tool_messages(agent.messages)[0]["content"]


def test_approved_edit_is_applied_and_preview_is_a_diff(workspace):
    target = workspace / "a.py"
    target.write_text("x = 1\n", encoding="utf-8")
    seen = []

    def approver(request):
        seen.append(request)
        return ApprovalChoice.YES

    client = FakeClient(
        [call("replace", path="a.py", old_string="x = 1", new_string="x = 2"), text("done")]
    )
    make_agent(client, approver=approver).run("change x")

    assert target.read_text(encoding="utf-8") == "x = 2\n"
    assert "-x = 1" in seen[0].preview and "+x = 2" in seen[0].preview


def test_always_allow_skips_later_prompts(workspace):
    target = workspace / "a.py"
    target.write_text("a\nb\n", encoding="utf-8")
    asked = []

    def approver(request):
        asked.append(request.tool_name)
        return ApprovalChoice.ALWAYS

    client = FakeClient(
        [
            call("replace", path="a.py", old_string="a", new_string="A"),
            call("replace", call_id="call_2", path="a.py", old_string="b", new_string="B"),
            text("done"),
        ]
    )
    make_agent(client, approver=approver).run("uppercase")

    assert target.read_text(encoding="utf-8") == "A\nB\n"
    assert asked == ["replace"]


def test_accept_edits_mode_runs_edits_without_asking(workspace):
    client = FakeClient([call("write_file", path="new.txt", content="hello"), text("ok")])
    make_agent(client, mode=PermissionMode.ACCEPT_EDITS).run("create")

    assert (workspace / "new.txt").read_text(encoding="utf-8") == "hello"


def test_unsafe_shell_command_is_denied_even_in_bypass(workspace):
    # The safety check uses OS-specific patterns
    dangerous = "format C:" if os.name == "nt" else "rm -rf /"
    client = FakeClient([call("run_shell_command", command=dangerous), text("ok")])
    agent = make_agent(client, mode=PermissionMode.BYPASS)

    agent.run("clean everything")

    assert "blocked by safety check" in tool_messages(agent.messages)[0]["content"]


def test_unknown_tool_and_bad_arguments_are_reported(workspace):
    client = FakeClient(
        [
            AssistantTurn(
                tool_calls=[
                    ToolCall(id="c1", name="does_not_exist", arguments="{}"),
                    ToolCall(id="c2", name="read_file", arguments="{not json"),
                ]
            ),
            text("sorry"),
        ]
    )
    agent = make_agent(client)
    agent.run("go")

    results = tool_messages(agent.messages)
    assert "unknown tool" in results[0]["content"]
    assert "invalid arguments" in results[1]["content"]


def test_stops_after_max_turns(workspace):
    (workspace / "f.txt").write_text("x", encoding="utf-8")
    turns = [call("read_file", call_id=f"c{i}", path="f.txt") for i in range(3)]
    agent = make_agent(FakeClient(turns), max_turns=3)

    response = agent.run("loop forever")

    assert response.metadata["stopped"] == "max_turns"
    assert "Stopped after 3 turns" in response.text


def test_interrupt_leaves_history_valid(workspace):
    def boom():
        raise KeyboardInterrupt

    client = FakeClient(
        [
            AssistantTurn(
                tool_calls=[
                    ToolCall(id="c1", name="boom", arguments="{}"),
                    ToolCall(id="c2", name="boom", arguments="{}"),
                ]
            )
        ]
    )
    agent = make_agent(client)
    agent._local_tools["boom"] = ToolSpec(
        name="boom",
        description="raises",
        parameters={"type": "object", "properties": {}},
        function=boom,
    )

    with pytest.raises(KeyboardInterrupt):
        agent.run("go")

    ids = [m["tool_call_id"] for m in tool_messages(agent.messages)]
    assert ids == ["c1", "c2"]


def test_task_tool_runs_read_only_subagent(workspace):
    (workspace / "deep.txt").write_text("needle", encoding="utf-8")
    client = FakeClient(
        [
            call("task", description="find needle", prompt="find the needle"),
            # sub-agent turns
            call("read_file", call_id="s1", path="deep.txt"),
            text("The needle is in deep.txt"),
            # back to the parent
            text("Found it in deep.txt."),
        ]
    )
    events = RecordingEvents()
    agent = make_agent(client, events=events)

    response = agent.run("where is the needle?")

    assert response.text == "Found it in deep.txt."
    assert "The needle is in deep.txt" in tool_messages(agent.messages)[0]["content"]
    assert "find needle › read_file" in events.started
    # The sub-agent is not offered the task tool
    sub_tools = {tool["function"]["name"] for tool in client.tools_offered[1]}
    assert "task" not in sub_tools


def test_streamed_text_reaches_events(workspace):
    events = RecordingEvents()
    make_agent(FakeClient([text("hello there")]), events=events).run("hi")
    assert "".join(events.text) == "hello there"


def test_conversation_continues_across_runs(workspace):
    client = FakeClient([text("first"), text("second")])
    agent = make_agent(client)
    agent.run("one")
    agent.run("two")

    contents = [m["content"] for m in client.requests[1] if m["role"] == "user"]
    assert contents == ["one", "two"]


def test_set_mode_updates_system_prompt(workspace):
    agent = Agent(
        client=FakeClient([]),
        permissions=PermissionManager(PermissionMode.DEFAULT),
    )
    assert "PLAN mode" not in agent.messages[0]["content"]
    agent.set_mode(PermissionMode.PLAN)
    assert "PLAN mode" in agent.messages[0]["content"]


# --------------------------------------------------------------- compaction


def test_compaction_keeps_recent_turns_and_tool_pairs():
    messages = [
        {"role": "system", "content": "sys"},
        {"role": "user", "content": "old question"},
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {"id": "c1", "type": "function", "function": {"name": "glob", "arguments": "{}"}}
            ],
        },
        {"role": "tool", "tool_call_id": "c1", "content": "files"},
        {"role": "assistant", "content": "old answer"},
        {"role": "user", "content": "recent 1"},
        {"role": "assistant", "content": "r1"},
        {"role": "user", "content": "recent 2"},
    ]
    assert find_split_index(messages, keep_recent=2) == 5

    compacted = compact_messages(messages, FakeClient([text("summary of old")]), keep_recent=2)

    assert compacted[0]["content"] == "sys"
    assert compacted[1]["content"] == SUMMARY_PREFIX + "summary of old"
    assert [m["content"] for m in compacted[2:]] == ["recent 1", "r1", "recent 2"]


def test_agent_compacts_when_context_is_full(workspace):
    client = FakeClient([text("a1"), text("a2"), text("summary"), text("a3")])
    agent = make_agent(client, context_window=200, compact_threshold=0.5)
    agent.run("x" * 100)
    agent.run("y" * 100)
    agent.run("z" * 100)

    assert any(SUMMARY_PREFIX in (m.get("content") or "") for m in agent.messages)


def test_truncate_output_keeps_head_and_tail():
    out = truncate_output("a" * 50 + "b" * 50, 20)
    assert out.startswith("a" * 12) and out.endswith("b" * 8)
    assert "characters omitted" in out


# -------------------------------------------------------------- permissions


@pytest.mark.parametrize(
    "command,key",
    [
        ("git status", "git status"),
        ("pytest -q", "pytest"),
        ("npm run test", "npm run"),
        ("git status && rm -rf build", ""),
        ("cat a | grep b", ""),
        ("echo hi > out.txt", ""),
    ],
)
def test_command_key(command, key):
    assert command_key(command) == key


def test_permission_mode_from_string():
    assert PermissionMode.from_string("accept-edits") is PermissionMode.ACCEPT_EDITS
    with pytest.raises(ValueError):
        PermissionMode.from_string("yolo")


# --------------------------------------------------------------- llm client


def test_streaming_accumulates_text_and_tool_call_fragments():
    def chunk(content=None, tool_calls=None, finish=None, usage=None):
        choices = (
            []
            if usage
            else [
                SimpleNamespace(
                    delta=SimpleNamespace(content=content, tool_calls=tool_calls),
                    finish_reason=finish,
                )
            ]
        )
        return SimpleNamespace(choices=choices, usage=usage)

    def frag(index, id=None, name=None, args=None):
        return SimpleNamespace(
            index=index, id=id, function=SimpleNamespace(name=name, arguments=args)
        )

    chunks = [
        chunk(content="Let me "),
        chunk(content="look."),
        chunk(tool_calls=[frag(0, id="c1", name="read_file", args='{"pa')]),
        chunk(tool_calls=[frag(0, args='th": "a.py"}')]),
        chunk(tool_calls=[frag(1, id="c2", name="glob", args="{}")], finish="tool_calls"),
        chunk(usage=SimpleNamespace(prompt_tokens=10, completion_tokens=5, total_tokens=15)),
    ]

    client = OpenAIChatClient.__new__(OpenAIChatClient)
    client.model = "m"
    client.extra_headers = {}
    client.extra_body = {}
    client.cache_breakpoints = False
    client._client = SimpleNamespace(
        chat=SimpleNamespace(completions=SimpleNamespace(create=lambda **kw: iter(chunks)))
    )
    streamed = []

    turn = client.complete([{"role": "user", "content": "hi"}], on_text=streamed.append)

    assert turn.content == "Let me look." == "".join(streamed)
    assert [(tc.id, tc.name) for tc in turn.tool_calls] == [("c1", "read_file"), ("c2", "glob")]
    assert turn.tool_calls[0].parsed_arguments() == {"path": "a.py"}
    assert turn.finish_reason == "tool_calls"
    assert turn.usage["total_tokens"] == 15


# ------------------------------------------------------------ shell blocklist


@pytest.mark.parametrize(
    "command,allowed",
    [
        ("ruff format src", True),
        ("git log --format=%H -n 1", True),
        ("rm -rf /tmp/build", True),
        ("echo halting", True),
        ("format C:", False),
        ("FORMAT.EXE C:", False),
        ("rm -rf /", False),
        ("ls && sudo shutdown now", False),
        ("mkfs.ext4 /dev/sda1", False),
        ("cd / ; rm -rf /*", False),
    ],
)
def test_shell_blocklist_matches_commands_not_substrings(command, allowed):
    from joshu.tools.shell_tool import is_command_allowed

    assert is_command_allowed(command)[0] is allowed


# --------------------------------------------------------------------- CLI


def _invoke_run(args, client=None, error=None):
    from typer.testing import CliRunner

    from joshu.ui.cli import app

    def fake_create(model=None, provider=None):
        if error:
            raise error
        return client

    with patch("joshu.core.agent.create_chat_client", side_effect=fake_create):
        return CliRunner().invoke(app, ["run", *args])


def test_cli_print_mode_outputs_only_the_answer(workspace):
    result = _invoke_run(["-p", "say hi"], client=FakeClient([text("hi there")]))

    assert result.exit_code == 0
    assert result.stdout.strip() == "hi there"


def test_cli_json_output(workspace):
    (workspace / "a.txt").write_text("data", encoding="utf-8")
    client = FakeClient([call("read_file", path="a.txt"), text("read it")])

    result = _invoke_run(["--output-format", "json", "read a.txt"], client=client)

    assert result.exit_code == 0
    payload = json.loads(result.stdout.strip().splitlines()[-1])
    assert payload["result"] == "read it"
    assert payload["tool_calls"] == 1 and payload["turns"] == 2


def test_cli_headless_denies_edits(workspace):
    client = FakeClient([call("write_file", path="x.txt", content="x"), text("could not")])

    result = _invoke_run(["-p", "write x"], client=client)

    assert result.exit_code == 0
    assert not (workspace / "x.txt").exists()


def test_cli_reports_missing_endpoint(workspace):
    result = _invoke_run(["-p", "hi"], error=LLMError("No model endpoint configured."))

    assert result.exit_code == 1


# ---------------------------------------------------------- endpoint fallback


class _Endpoint:
    def __init__(self, model, error=None):
        self.model = model
        self.error = error
        self.calls = 0

    def complete(self, messages, tools=None, **kwargs):
        self.calls += 1
        if self.error:
            raise self.error
        return text(f"from {self.model}")


def test_fallback_skips_unreachable_endpoint_and_remembers():
    from joshu.core.llm_client import FallbackChatClient

    dead = _Endpoint("dead", LLMError("down", unreachable=True))
    live = _Endpoint("live")
    client = FallbackChatClient([dead, live])

    assert client.complete([]).content == "from live"
    assert client.complete([]).content == "from live"
    assert dead.calls == 1 and client.model == "live"


def test_fallback_does_not_hide_request_errors():
    from joshu.core.llm_client import FallbackChatClient

    bad = _Endpoint("bad", LLMError("401 invalid key"))
    live = _Endpoint("live")

    with pytest.raises(LLMError, match="invalid key"):
        FallbackChatClient([bad, live]).complete([])
    assert live.calls == 0


def test_tool_result_summaries():
    from joshu.ui.agent_ui import _first_line, summarize_arguments

    assert _first_line('{"success": true, "files": ["a", "b"]}', 80) == "2 files"
    assert _first_line('{"success": false, "error": "File not found: x"}', 80) == (
        "File not found: x"
    )
    assert _first_line("plain\ntext", 80) == "plain"
    assert summarize_arguments("run_shell_command", {"command": "pytest -q"}) == "pytest -q"
