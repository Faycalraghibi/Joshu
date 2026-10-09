"""Tests for prompt-cache breakpoints and cached-token reporting."""

from types import SimpleNamespace

from joshu.core.llm_client import OpenAIChatClient, _usage_dict, create_chat_client
from joshu.core.prompt_cache import (
    EPHEMERAL,
    add_cache_breakpoints,
    model_wants_breakpoints,
)
from joshu.core.providers import BUILTIN_PROVIDERS


def test_breakpoints_on_system_and_last_user_message():
    messages = [
        {"role": "system", "content": "sys"},
        {"role": "user", "content": "first"},
        {"role": "assistant", "content": "a"},
        {"role": "user", "content": "second"},
        {"role": "assistant", "content": "", "tool_calls": []},
        {"role": "tool", "tool_call_id": "c1", "content": "out"},
    ]
    marked = add_cache_breakpoints(messages)

    assert marked[0]["content"] == [{"type": "text", "text": "sys", "cache_control": EPHEMERAL}]
    assert marked[3]["content"] == [{"type": "text", "text": "second", "cache_control": EPHEMERAL}]
    assert marked[1]["content"] == "first" and marked[5]["content"] == "out"
    assert messages[0]["content"] == "sys"  # the input is not modified


def test_breakpoint_goes_on_the_text_part_of_a_multipart_message():
    image = {"type": "image_url", "image_url": {"url": "data:image/png;base64,AAAA"}}
    messages = [{"role": "user", "content": [{"type": "text", "text": "look"}, image]}]
    marked = add_cache_breakpoints(messages)

    assert marked[0]["content"][0]["cache_control"] == EPHEMERAL
    assert "cache_control" not in marked[0]["content"][1]
    assert "cache_control" not in messages[0]["content"][0]


def test_model_patterns():
    assert model_wants_breakpoints("anthropic/claude-sonnet-5-5", ["anthropic/"])
    assert not model_wants_breakpoints("openai/gpt-4.1", ["anthropic/"])
    assert model_wants_breakpoints("anything", ["*"])
    assert not model_wants_breakpoints("anything", [])


def test_openrouter_enables_breakpoints_only_for_anthropic_models(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "k")
    assert BUILTIN_PROVIDERS["openrouter"].cache_control_models == ["anthropic/"]
    assert create_chat_client("anthropic/claude-sonnet-5-5", "openrouter").cache_breakpoints
    assert not create_chat_client("poolside/laguna-s-2.1:free", "openrouter").cache_breakpoints


def test_client_sends_marked_messages():
    sent = {}

    def create(**request):
        sent.update(request)
        delta = SimpleNamespace(content="ok", tool_calls=None)
        return iter(
            [
                SimpleNamespace(
                    choices=[SimpleNamespace(delta=delta, finish_reason="stop")], usage=None
                )
            ]
        )

    client = OpenAIChatClient.__new__(OpenAIChatClient)
    client.model = "anthropic/claude"
    client.base_url = "x"
    client.extra_headers = {}
    client.extra_body = {}
    client.cache_breakpoints = True
    client._client = SimpleNamespace(
        chat=SimpleNamespace(completions=SimpleNamespace(create=create))
    )

    client.complete([{"role": "system", "content": "s"}, {"role": "user", "content": "u"}])
    assert sent["messages"][1]["content"][0]["cache_control"] == EPHEMERAL


def test_cached_tokens_are_read_from_usage():
    usage = SimpleNamespace(
        prompt_tokens=1000,
        completion_tokens=10,
        total_tokens=1010,
        prompt_tokens_details=SimpleNamespace(cached_tokens=800),
    )
    assert _usage_dict(usage)["cached_tokens"] == 800
    plain = SimpleNamespace(prompt_tokens=1, completion_tokens=1, total_tokens=2)
    assert "cached_tokens" not in _usage_dict(plain)
