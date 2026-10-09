"""The thinking setting: reasoning switched off where it mostly costs time."""

import json
from types import SimpleNamespace

import pytest
from test_agent_loop import call, make_agent, text

from joshu.core.config import get_config_manager
from joshu.core.llm_client import OpenAIChatClient, _merged
from joshu.core.providers import get_providers


class RecordingClient:
    model = "fake-model"

    def __init__(self, turns):
        self.turns = list(turns)
        self.thinking = []

    def complete(self, messages, tools=None, **kwargs):
        self.thinking.append(kwargs.get("thinking", True))
        return self.turns.pop(0)


def test_merged_lays_nested_fields_over():
    base = {"usage": {"include": True}, "chat_template_kwargs": {"a": 1}}
    out = _merged(base, {"chat_template_kwargs": {"enable_thinking": False}})
    assert out == {
        "usage": {"include": True},
        "chat_template_kwargs": {"a": 1, "enable_thinking": False},
    }
    assert base["chat_template_kwargs"] == {"a": 1}  # not modified


def test_client_sends_the_switch_only_when_asked():
    client = OpenAIChatClient(
        "http://x/v1",
        "key",
        "m",
        extra_body={"usage": {"include": True}},
        no_thinking_options={"chat_template_kwargs": {"enable_thinking": False}},
    )
    sent = []

    def create(**request):
        sent.append(request)
        delta = SimpleNamespace(content="ok", tool_calls=None, reasoning_content=None)
        return iter(
            [
                SimpleNamespace(
                    choices=[SimpleNamespace(delta=delta, finish_reason="stop")], usage=None
                )
            ]
        )

    client._client = SimpleNamespace(
        chat=SimpleNamespace(completions=SimpleNamespace(create=create))
    )
    client.complete([{"role": "user", "content": "hi"}])
    client.complete([{"role": "user", "content": "hi"}], thinking=False)
    assert sent[0]["extra_body"] == {"usage": {"include": True}}
    assert sent[1]["extra_body"]["chat_template_kwargs"] == {"enable_thinking": False}
    assert sent[1]["extra_body"]["usage"] == {"include": True}


def test_providers_know_their_switch():
    providers = get_providers()
    assert providers["nvidia"].no_thinking_options == {
        "chat_template_kwargs": {"enable_thinking": False}
    }
    assert providers["openai"].no_thinking_options == {}
    custom = get_providers(
        {"mine": {"base_url": "http://h/v1", "no_thinking_options": {"think": False}}}
    )
    assert custom["mine"].no_thinking_options == {"think": False}


def read(path, call_id):
    return call("read_file", call_id=call_id, path=path)


@pytest.mark.parametrize(
    "setting, expected",
    [
        # first call, after a successful read, after a failed read, final answer
        ("on", [True, True, True, True]),
        ("off", [False, False, False, False]),
        ("auto", [True, False, True, True]),
    ],
)
def test_agent_chooses_per_call(tmp_path, setting, expected):
    from joshu.tools import filesystem_tools

    filesystem_tools.set_workspace_root(tmp_path)
    try:
        (tmp_path / "a.py").write_text("x = 1\n", encoding="utf-8")
        get_config_manager().set("thinking", setting)
        client = RecordingClient(
            [
                read("a.py", "c1"),
                read("missing.py", "c2"),
                call("write_file", call_id="c3", path="b.py", content="y"),
                text("done"),
            ]
        )
        from joshu.core.permissions import PermissionMode

        make_agent(client, mode=PermissionMode.BYPASS, cwd=tmp_path).run("go")
        # calls: start, after read ok, after read failed, after write -> 4 calls
        assert client.thinking == expected
    finally:
        filesystem_tools._workspace_root = None


def test_auto_thinks_after_a_sub_agent_or_shell_result(tmp_path):
    get_config_manager().set("thinking", "auto")
    client = RecordingClient([call("run_shell_command", command="echo hi"), text("done")])
    from joshu.core.permissions import PermissionMode

    make_agent(client, mode=PermissionMode.BYPASS, cwd=tmp_path).run("go")
    assert client.thinking == [True, True]
    assert json.dumps(client.thinking)
