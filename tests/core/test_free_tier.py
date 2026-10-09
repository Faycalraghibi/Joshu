"""Retries, failover to other models, model checks and quiet subcommands."""

from unittest.mock import MagicMock, patch

import httpx
import openai
import pytest
from typer.testing import CliRunner

from joshu.core.config import get_config_manager
from joshu.core.llm_client import (
    AssistantTurn,
    FallbackChatClient,
    LLMError,
    OpenAIChatClient,
    ToolCall,
    create_chat_client,
)
from joshu.core.model_catalog import check_model
from joshu.core.providers import BUILTIN_PROVIDERS


def status_error(code):
    request = httpx.Request("POST", "https://example.test/v1/chat/completions")
    response = httpx.Response(code, request=request, json={"error": "x"})
    return openai.APIStatusError(f"status {code}", response=response, body=None)


def failing_client(error):
    client = OpenAIChatClient("https://example.test/v1", "k", "m", max_retries=0)
    client._client = MagicMock()
    client._client.chat.completions.create.side_effect = error
    return client


def run(args):
    from joshu.ui.cli import app

    return CliRunner().invoke(app, args)


# ----------------------------------------------------------- error classes


@pytest.mark.parametrize("code", [404, 429, 500, 503])
def test_status_errors_another_model_may_handle_are_unavailable(code):
    with pytest.raises(LLMError) as info:
        failing_client(status_error(code)).complete([{"role": "user", "content": "hi"}])
    assert info.value.unavailable and not info.value.unreachable


@pytest.mark.parametrize("code", [400, 401, 403])
def test_request_errors_are_not_unavailable(code):
    with pytest.raises(LLMError) as info:
        failing_client(status_error(code)).complete([{"role": "user", "content": "hi"}])
    assert not info.value.unavailable


def test_timeouts_are_unreachable_and_unavailable():
    request = httpx.Request("POST", "https://example.test/v1/chat/completions")
    with pytest.raises(LLMError) as info:
        failing_client(openai.APITimeoutError(request=request)).complete([])
    assert info.value.unreachable and info.value.unavailable


def test_fallback_moves_on_from_unavailable_model():
    busy = MagicMock(model="busy")
    busy.complete.side_effect = LLMError("429", unavailable=True)
    live = MagicMock(model="live")
    live.complete.return_value = AssistantTurn(content="ok")

    assert FallbackChatClient([busy, live]).complete([]).content == "ok"


# ------------------------------------------------------------ configuration


def test_retries_and_timeout_come_from_config(monkeypatch):
    monkeypatch.setenv("NVIDIA_API_KEY", "nvapi-test")
    config = get_config_manager()
    config.set("request_retries", 5)
    config.set("request_timeout", 300)

    client = create_chat_client("nvidia/m1", provider="nvidia")

    assert client._client.max_retries == 5
    assert client._client.timeout.read == 300


def test_fallback_accepts_named_models(monkeypatch):
    monkeypatch.setenv("NVIDIA_API_KEY", "nvapi-test")
    config = get_config_manager()
    config.set("provider", "nvidia")
    config.set("model", "nvidia/big")
    config.set("models", {"small": {"provider": "nvidia", "model": "nvidia/small"}})
    config.set("fallback_providers", ["small", "nvidia"])

    client = create_chat_client()

    # `nvidia` would use its default model, which differs from both
    assert isinstance(client, FallbackChatClient)
    assert [c.model for c in client.clients][:2] == ["nvidia/big", "nvidia/small"]


# ----------------------------------------------------------------- checks


def _turn(calls):
    return AssistantTurn(tool_calls=[ToolCall("1", name, "{}") for name in calls])


def test_check_model_reports_tool_calling(monkeypatch):
    monkeypatch.setenv("NVIDIA_API_KEY", "nvapi-test")
    with patch.object(OpenAIChatClient, "complete", return_value=_turn(["ping"])):
        result = check_model(BUILTIN_PROVIDERS["nvidia"], "nvidia/m1")
    assert result.ok and result.tool_call

    with patch.object(OpenAIChatClient, "complete", return_value=_turn([])):
        result = check_model(BUILTIN_PROVIDERS["nvidia"], "nvidia/m1")
    assert result.ok and not result.tool_call


def test_check_model_reports_failures(monkeypatch):
    monkeypatch.setenv("NVIDIA_API_KEY", "nvapi-test")
    with patch.object(OpenAIChatClient, "complete", side_effect=LLMError("404 Not Found")):
        result = check_model(BUILTIN_PROVIDERS["nvidia"], "nvidia/m1")
    assert not result.ok and "404" in result.error


def test_use_check_failure_saves_nothing(monkeypatch):
    monkeypatch.setenv("NVIDIA_API_KEY", "nvapi-test")
    listed = httpx.Response(
        200, json={"data": [{"id": "nvidia/m1"}]}, request=httpx.Request("GET", "https://x")
    )
    with (
        patch("httpx.get", return_value=listed),
        patch.object(OpenAIChatClient, "complete", side_effect=LLMError("404 Not Found")),
    ):
        result = run(["use", "nvidia/m1", "-p", "nvidia", "--check"])
    assert result.exit_code == 1
    assert "didn't answer" in result.stdout
    assert get_config_manager().get("model") != "nvidia/m1"


def test_models_check_command(monkeypatch):
    monkeypatch.setenv("NVIDIA_API_KEY", "nvapi-test")
    with patch.object(OpenAIChatClient, "complete", return_value=_turn(["ping"])):
        result = run(["models", "check", "nvidia/m1", "-p", "nvidia"])
    assert result.exit_code == 0
    assert "works and calls tools" in result.stdout


# ------------------------------------------------------------------ banner


def test_non_conversation_commands_print_no_banner():
    with patch("joshu.ui.cli.print_banner") as banner:
        run(["providers"])
    assert not banner.called


def test_a_request_is_streamed_even_when_nothing_is_shown():
    """A blocking call must deliver the whole answer within the timeout, so a
    model that thinks for minutes failed in joshu run and -p; streamed, the
    timeout applies to each chunk."""
    from types import SimpleNamespace as NS

    def chunk(content=None, tool=None, finish=None, usage=None):
        delta = NS(content=content, tool_calls=[tool] if tool else None, reasoning_content=None)
        return NS(choices=[NS(delta=delta, finish_reason=finish)], usage=usage)

    call = NS(index=0, id="c1", function=NS(name="read_file", arguments='{"path": "a"}'))
    chunks = [chunk("Reading it."), chunk(tool=call), chunk(finish="tool_calls")]
    client = OpenAIChatClient("https://example.test/v1", "k", "m", max_retries=0)
    client._client = MagicMock()
    client._client.chat.completions.create.return_value = iter(chunks)
    turn = client.complete([{"role": "user", "content": "hi"}])  # no on_text
    assert client._client.chat.completions.create.call_args.kwargs["stream"] is True
    assert turn.content == "Reading it." and turn.finish_reason == "tool_calls"
    assert [(c.name, c.arguments) for c in turn.tool_calls] == [("read_file", '{"path": "a"}')]
