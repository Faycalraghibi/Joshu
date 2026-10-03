"""Tests for model listing, named models and the provider/model commands."""

from unittest.mock import MagicMock, patch

import httpx
import pytest
from typer.testing import CliRunner

from joshu.core.agent import Agent
from joshu.core.config import get_config_manager
from joshu.core.llm_client import create_chat_client
from joshu.core.model_catalog import (
    CatalogError,
    ModelInfo,
    filter_models,
    list_models,
    named_models,
)
from joshu.core.permissions import PermissionManager
from joshu.core.providers import BUILTIN_PROVIDERS

OPENROUTER_LIST = {
    "data": [
        {
            "id": "nvidia/nemotron-3-super-120b-a12b:free",
            "context_length": 262144,
            "supported_parameters": ["tools", "temperature"],
            "pricing": {"prompt": "0", "completion": "0"},
        },
        {
            "id": "acme/no-tools",
            "context_length": 8192,
            "supported_parameters": ["temperature"],
            "pricing": {"prompt": "0.000001", "completion": "0.000002"},
        },
    ]
}


def fake_get(payload, status=200, seen=None):
    def get(url, headers=None, timeout=None):
        if seen is not None:
            seen.update(url=url, headers=headers or {})
        request = httpx.Request("GET", url)
        return httpx.Response(status, json=payload, request=request)

    return get


def run(args):
    from joshu.ui.cli import app

    return CliRunner().invoke(app, args)


# ---------------------------------------------------------------- listing


def test_list_models_reads_openrouter_metadata(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "k")
    seen = {}
    with patch("httpx.get", fake_get(OPENROUTER_LIST, seen=seen)):
        models = list_models(BUILTIN_PROVIDERS["openrouter"])

    assert seen["url"] == "https://openrouter.ai/api/v1/models"
    assert seen["headers"]["Authorization"] == "Bearer k"
    assert models[1] == ModelInfo("nvidia/nemotron-3-super-120b-a12b:free", 262144, True, True)
    assert models[0] == ModelInfo("acme/no-tools", 8192, False, False)


def test_list_models_without_metadata_marks_unknown(monkeypatch):
    monkeypatch.delenv("NVIDIA_API_KEY", raising=False)
    payload = {"data": [{"id": "nvidia/nemotron-3.5-lightning-30b-a3b", "object": "model"}]}
    with patch("httpx.get", fake_get(payload)):
        [model] = list_models(BUILTIN_PROVIDERS["nvidia"])
    assert (model.tools, model.free, model.context_length) == (None, None, None)


def test_list_models_errors_become_catalog_errors():
    with patch("httpx.get", fake_get({"error": "nope"}, status=401)):
        with pytest.raises(CatalogError, match="Could not list models"):
            list_models(BUILTIN_PROVIDERS["nvidia"])


def test_filters():
    models = [
        ModelInfo("nvidia/nemotron-a", tools=True, free=True),
        ModelInfo("nvidia/nemotron-b", tools=False, free=True),
        ModelInfo("meta/llama", tools=None, free=False),
    ]
    assert [m.id for m in filter_models(models, "nemotron")] == [
        "nvidia/nemotron-a",
        "nvidia/nemotron-b",
    ]
    assert [m.id for m in filter_models(models, tools_only=True)] == [
        "nvidia/nemotron-a",
        "meta/llama",
    ]
    assert [m.id for m in filter_models(models, free_only=True)] == [
        "nvidia/nemotron-a",
        "nvidia/nemotron-b",
    ]


# ---------------------------------------------------------- named models


def test_named_models_parse_and_skip_invalid():
    named = named_models(
        {
            "fast": {"provider": "nvidia", "model": "m1", "context_window": 32000},
            "broken": {"model": "no-provider"},
        }
    )
    assert list(named) == ["fast"]
    assert named["fast"].context_window == 32000


def test_named_model_brings_provider_model_and_context_window(monkeypatch):
    monkeypatch.setenv("NVIDIA_API_KEY", "nvapi-test")
    get_config_manager().set(
        "models", {"fast": {"provider": "nvidia", "model": "nvidia/m1", "context_window": 32000}}
    )

    client = create_chat_client("fast")

    assert client.base_url == "https://integrate.api.nvidia.com/v1"
    assert client.model == "nvidia/m1"
    agent = Agent(client=client, permissions=PermissionManager(), system_prompt="s")
    assert agent.context_window == 32000


def test_nvidia_preset():
    nvidia = BUILTIN_PROVIDERS["nvidia"]
    assert nvidia.base_url == "https://integrate.api.nvidia.com/v1"
    assert nvidia.api_key_env == "NVIDIA_API_KEY"


# ---------------------------------------------------------------- commands


def test_providers_add_and_remove():
    assert (
        run(["providers", "add", "homelab", "--base-url", "http://10.0.0.5:8080/v1"]).exit_code == 0
    )
    assert get_config_manager().get("providers")["homelab"] == {
        "base_url": "http://10.0.0.5:8080/v1"
    }
    assert "homelab" in run(["providers"]).stdout

    assert run(["providers", "remove", "homelab"]).exit_code == 0
    assert "homelab" not in get_config_manager().get("providers")


def test_models_command_lists_and_filters(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "k")
    with patch("httpx.get", fake_get(OPENROUTER_LIST)):
        result = run(["models", "--provider", "openrouter", "--tools"])
    assert result.exit_code == 0
    assert "nemotron-3-super" in result.stdout and "acme/no-tools" not in result.stdout


def test_models_add_and_use_named_model():
    with patch("httpx.get", fake_get({"data": [{"id": "nvidia/m1"}]})):
        assert run(["models", "add", "fast", "nvidia/m1", "--provider", "nvidia"]).exit_code == 0
        assert run(["use", "fast"]).exit_code == 0

    config = get_config_manager()
    assert config.get("models")["fast"] == {"provider": "nvidia", "model": "nvidia/m1"}
    assert config.get("model") == "fast"


def test_use_sets_provider_and_model_and_warns_about_unknown_ids():
    with patch("httpx.get", fake_get({"data": [{"id": "nvidia/real"}]})):
        result = run(["use", "nvidia/typo", "--provider", "nvidia"])
    assert result.exit_code == 0
    assert "doesn't list 'nvidia/typo'" in result.stdout
    config = get_config_manager()
    assert (config.get("provider"), config.get("model")) == ("nvidia", "nvidia/typo")


def test_use_warns_when_model_lacks_tool_calling(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "k")
    with patch("httpx.get", fake_get(OPENROUTER_LIST)):
        result = run(["use", "acme/no-tools", "--provider", "openrouter"])
    assert "doesn't support tool calling" in result.stdout


def test_interactive_models_command(monkeypatch):
    from joshu.ui.interactive.commands import CommandHandler

    monkeypatch.setenv("OPENROUTER_API_KEY", "k")
    get_config_manager().set("provider", "openrouter")
    mode = MagicMock()
    mode.config_manager = get_config_manager()
    with patch("httpx.get", fake_get(OPENROUTER_LIST)):
        CommandHandler(mode).handle_slash_command("/models nemotron")
    shown = mode._show_message.call_args[0][0]
    assert "nemotron-3-super-120b-a12b:free  (tools, free)" in shown
