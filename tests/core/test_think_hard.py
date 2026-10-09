""" "think hard" / "ultrathink" in a request: it always thinks, with high effort where possible."""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from test_agent_loop import FakeClient, call, make_agent, text

from joshu.core.agent import THINK_HARD
from joshu.core.llm_client import FallbackChatClient, OpenAIChatClient
from joshu.core.providers import BUILTIN_PROVIDERS
from joshu.tools import filesystem_tools


@pytest.fixture
def workspace(tmp_path):
    filesystem_tools.set_workspace_root(tmp_path)
    yield tmp_path
    filesystem_tools._workspace_root = None


class Recording(FakeClient):
    def __init__(self, turns):
        super().__init__(turns)
        self.options = []

    def complete(self, messages, tools=None, **kwargs):
        self.options.append({k: kwargs.get(k) for k in ("thinking", "effort")})
        return super().complete(messages, tools, **kwargs)


@pytest.mark.parametrize(
    "prompt, hard",
    [
        ("ultrathink: why does the cache leak?", True),
        ("Think hard about the edge cases", True),
        ("think harder", True),
        ("think really hard about it", True),
        ("I think the bug is in parse()", False),
        ("this is a hard problem", False),
    ],
)
def test_keywords(prompt, hard):
    assert bool(THINK_HARD.search(prompt)) is hard


def test_a_think_hard_request_always_thinks_with_high_effort(workspace):
    (workspace / "a.txt").write_text("a", encoding="utf-8")
    from joshu.core.config import get_config_manager

    get_config_manager().set("thinking", "off")
    client = Recording([call("read_file", path="a.txt"), text("Done.")])
    make_agent(client).run("ultrathink: what is in a.txt?")
    assert client.options == [{"thinking": None, "effort": "high"}] * 2

    client = Recording([call("read_file", path="a.txt"), text("Done.")])
    make_agent(client).run("what is in a.txt?")  # thinking off, no keyword
    assert all(o == {"thinking": False, "effort": None} for o in client.options)


def test_the_client_sends_the_providers_high_effort_fields():
    sent = {}

    def create(**request):
        sent.clear()
        sent.update(request)
        delta = SimpleNamespace(content="ok", tool_calls=None, reasoning_content=None)
        choice = SimpleNamespace(delta=delta, finish_reason="stop")
        return iter([SimpleNamespace(choices=[choice], usage=None)])

    client = OpenAIChatClient(
        "https://x/v1", "k", "m", high_effort_options={"reasoning": {"effort": "high"}}
    )
    client._client = MagicMock()
    client._client.chat.completions.create.side_effect = create
    client.complete([{"role": "user", "content": "hi"}], effort="high")
    assert sent["extra_body"] == {"reasoning": {"effort": "high"}}
    client.complete([{"role": "user", "content": "hi"}])
    assert "extra_body" not in sent
    assert BUILTIN_PROVIDERS["openrouter"].high_effort_options


def test_the_fallback_client_passes_thinking_and_effort_on():
    inner = MagicMock()
    inner.complete.return_value = "turn"
    fallback = FallbackChatClient([inner])
    fallback.complete([], thinking=False)  # raised TypeError before
    assert inner.complete.call_args.kwargs["thinking"] is False
    fallback.complete([], effort="high")
    assert inner.complete.call_args.kwargs["effort"] == "high"
    fallback.complete([])
    assert "thinking" not in inner.complete.call_args.kwargs
