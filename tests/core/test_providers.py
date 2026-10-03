"""Tests for the provider layer: presets, custom providers, client resolution."""

import pytest
from typer.testing import CliRunner

from joshu.core.config import get_config_manager
from joshu.core.llm_client import (
    FallbackChatClient,
    LLMError,
    OpenAIChatClient,
    create_chat_client,
)
from joshu.core.providers import (
    BUILTIN_PROVIDERS,
    ProviderError,
    configured_provider_names,
    get_providers,
)

KEY_VARS = [
    "OPENROUTER_API_KEY",
    "OPENAI_API_KEY",
    "ANTHROPIC_API_KEY",
    "MYCLOUD_API_KEY",
]


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    for var in KEY_VARS:
        monkeypatch.delenv(var, raising=False)


def configure(**values):
    config = get_config_manager()
    for key, value in values.items():
        assert config.set(key, value), key
    return config


# ------------------------------------------------------------------ registry


def test_builtin_presets_cover_common_providers():
    for name in ["openrouter", "openai", "anthropic", "gemini", "groq", "ollama", "lmstudio"]:
        assert name in BUILTIN_PROVIDERS


def test_override_builtin_and_add_custom():
    providers = get_providers(
        {
            "ollama": {"base_url": "http://gpu-box:11434/v1"},
            "mycloud": {
                "base_url": "https://api.mycloud.example/v1",
                "api_key_env": "MYCLOUD_API_KEY",
            },
            "homelab": {"base_url": "http://10.0.0.5:8080/v1"},
        }
    )
    assert providers["ollama"].base_url == "http://gpu-box:11434/v1"
    assert providers["mycloud"].requires_key is True
    assert providers["homelab"].requires_key is False


@pytest.mark.parametrize(
    "overrides,message",
    [
        ({"x": {"api_key_env": "X_KEY"}}, "needs a base_url"),
        ({"x": {"base_url": "http://x", "bogus": 1}}, "unknown settings: bogus"),
        ({"x": "http://x"}, "must be a mapping"),
    ],
)
def test_invalid_provider_config(overrides, message):
    with pytest.raises(ProviderError, match=message):
        get_providers(overrides)


def test_configured_provider_names(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "k")
    names = configured_provider_names(get_providers())
    assert "openai" in names and "ollama" in names and "anthropic" not in names


# ---------------------------------------------------------- client creation


def test_configured_provider_and_model_are_used(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    configure(provider="openai", model="gpt-test")

    client = create_chat_client()

    assert isinstance(client, OpenAIChatClient)
    assert client.base_url == "https://api.openai.com/v1"
    assert client.model == "gpt-test"


def test_missing_key_names_the_variable():
    configure(provider="anthropic", model="claude-sonnet-5-5")
    with pytest.raises(LLMError, match="set ANTHROPIC_API_KEY"):
        create_chat_client()


def test_explicit_provider_uses_its_default_model_not_the_configured_one(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "k")
    configure(provider="openrouter", model="poolside/laguna-s-2.1:free")

    client = create_chat_client(provider="anthropic")

    assert client.model == BUILTIN_PROVIDERS["anthropic"].default_model


def test_provider_without_model_is_an_error(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "k")
    with pytest.raises(LLMError, match="No model set for provider 'openai'"):
        create_chat_client(provider="openai")


def test_unknown_provider_lists_known_ones():
    with pytest.raises(LLMError, match="Unknown provider 'nope'.*openai"):
        create_chat_client(provider="nope")


def test_custom_local_provider_needs_no_key():
    configure(
        provider="homelab",
        model="qwen-coder",
        providers={"homelab": {"base_url": "http://10.0.0.5:8080/v1"}},
    )
    client = create_chat_client()
    assert client.base_url == "http://10.0.0.5:8080/v1" and client.model == "qwen-coder"


def test_fallback_providers_build_a_chain(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "k")
    configure(provider="ollama", model="llama3", fallback_providers=["openrouter", "openai"])

    client = create_chat_client()

    # openai is skipped: no key and no default model
    assert isinstance(client, FallbackChatClient)
    assert [c.model for c in client.clients] == [
        "llama3",
        BUILTIN_PROVIDERS["openrouter"].default_model,
    ]


# ---------------------------------------------------------------------- CLI


def test_providers_command_lists_presets(monkeypatch):
    from joshu.ui.cli import app

    monkeypatch.setenv("OPENAI_API_KEY", "k")
    result = CliRunner().invoke(app, ["providers"])

    assert result.exit_code == 0
    assert "anthropic" in result.stdout and "ollama" in result.stdout


def test_run_reports_unknown_provider():
    from joshu.ui.cli import app

    result = CliRunner().invoke(app, ["run", "-p", "--provider", "nope", "hi"])
    assert result.exit_code == 1
