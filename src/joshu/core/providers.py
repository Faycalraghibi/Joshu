"""
Model providers.

Joshu talks to every provider through the OpenAI-compatible chat API, which
nearly all providers (and local servers) expose. A provider is just a base URL,
where to find its API key, and optional headers. Common providers are built in;
any other is added under `providers:` in config.yaml:

    provider: mycloud
    model: some-model-id
    providers:
      mycloud:
        base_url: https://api.mycloud.example/v1
        api_key_env: MYCLOUD_API_KEY

Built-in entries can be overridden the same way (e.g. a different base_url).
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field, replace
from typing import Any, Dict, List, Optional

DEFAULT_PROVIDER = "nvidia"


@dataclass(frozen=True)
class Provider:
    """An OpenAI-compatible endpoint."""

    name: str
    base_url: str
    api_key_env: Optional[str] = None  # environment variable holding the key
    api_key: Optional[str] = None  # literal key (prefer api_key_env)
    headers: Dict[str, str] = field(default_factory=dict)
    default_model: Optional[str] = None
    requires_key: bool = True  # local servers don't need one
    description: str = ""
    # Extra fields sent with every request (OpenAI SDK extra_body)
    request_options: Dict[str, Any] = field(default_factory=dict)
    # Model id prefixes ("*" = all) whose requests get prompt-cache breakpoints
    cache_control_models: List[str] = field(default_factory=list)
    # Extra fields that turn a reasoning model's thinking off for one request
    # (the `thinking` setting); empty when the provider has no such switch
    no_thinking_options: Dict[str, Any] = field(default_factory=dict)

    def resolve_api_key(self) -> Optional[str]:
        """The API key, from the config value or the environment."""
        if self.api_key:
            return self.api_key
        if self.api_key_env:
            return os.getenv(self.api_key_env) or None
        return None

    def is_configured(self) -> bool:
        """True when the provider can be used (has a key, or needs none)."""
        return not self.requires_key or self.resolve_api_key() is not None


BUILTIN_PROVIDERS: Dict[str, Provider] = {
    p.name: p
    for p in [
        Provider(
            "openrouter",
            "https://openrouter.ai/api/v1",
            api_key_env="OPENROUTER_API_KEY",
            headers={"X-Title": "Joshu Assistant"},
            request_options={"usage": {"include": True}},  # cost in every response
            cache_control_models=["anthropic/"],  # Anthropic needs explicit breakpoints
            no_thinking_options={"reasoning": {"enabled": False}},
            default_model="poolside/laguna-s-2.1:free",
            description="Hundreds of models from many vendors behind one key",
        ),
        Provider(
            "openai",
            "https://api.openai.com/v1",
            api_key_env="OPENAI_API_KEY",
            description="OpenAI",
        ),
        Provider(
            "anthropic",
            "https://api.anthropic.com/v1/",
            api_key_env="ANTHROPIC_API_KEY",
            default_model="claude-sonnet-5-5",
            description="Anthropic Claude (OpenAI SDK compatibility endpoint)",
        ),
        Provider(
            "gemini",
            "https://generativelanguage.googleapis.com/v1beta/openai/",
            api_key_env="GEMINI_API_KEY",
            description="Google Gemini (OpenAI compatibility endpoint)",
        ),
        Provider(
            "groq",
            "https://api.groq.com/openai/v1",
            api_key_env="GROQ_API_KEY",
            description="Groq",
        ),
        Provider(
            "mistral",
            "https://api.mistral.ai/v1",
            api_key_env="MISTRAL_API_KEY",
            default_model="mistral-large-latest",
            description="Mistral AI",
        ),
        Provider(
            "deepseek",
            "https://api.deepseek.com/v1",
            api_key_env="DEEPSEEK_API_KEY",
            default_model="deepseek-chat",
            description="DeepSeek platform",
        ),
        Provider("xai", "https://api.x.ai/v1", api_key_env="XAI_API_KEY", description="xAI"),
        Provider(
            "together",
            "https://api.together.xyz/v1",
            api_key_env="TOGETHER_API_KEY",
            description="Together AI",
        ),
        Provider(
            "fireworks",
            "https://api.fireworks.ai/inference/v1",
            api_key_env="FIREWORKS_API_KEY",
            description="Fireworks AI",
        ),
        Provider(
            "cerebras",
            "https://api.cerebras.ai/v1",
            api_key_env="CEREBRAS_API_KEY",
            description="Cerebras",
        ),
        Provider(
            "nvidia",
            "https://integrate.api.nvidia.com/v1",
            api_key_env="NVIDIA_API_KEY",
            default_model="nvidia/nemotron-3.5-lightning-30b-a3b",
            description="NVIDIA-hosted open models (free key from build.nvidia.com)",
            no_thinking_options={"chat_template_kwargs": {"enable_thinking": False}},
        ),
        Provider(
            "ollama",
            "http://localhost:11434/v1",
            requires_key=False,
            description="Local models served by Ollama",
        ),
        Provider(
            "lmstudio",
            "http://localhost:1234/v1",
            requires_key=False,
            description="Local models served by LM Studio",
        ),
        Provider(
            "vllm",
            "http://localhost:8000/v1",
            requires_key=False,
            description="vLLM OpenAI-compatible server",
            no_thinking_options={"chat_template_kwargs": {"enable_thinking": False}},
        ),
    ]
}

_PROVIDER_FIELDS = {
    "base_url",
    "api_key_env",
    "api_key",
    "headers",
    "default_model",
    "requires_key",
    "description",
    "request_options",
    "cache_control_models",
    "no_thinking_options",
}


class ProviderError(ValueError):
    """Invalid or unknown provider configuration."""


def get_providers(overrides: Optional[Dict[str, Any]] = None) -> Dict[str, Provider]:
    """
    Built-in providers merged with entries from config.

    Args:
        overrides: The `providers:` config mapping (name -> fields). Fields of a
            built-in provider are overridden; new names define custom providers,
            which need at least `base_url`.

    Raises:
        ProviderError: for malformed entries.
    """
    providers = dict(BUILTIN_PROVIDERS)
    for name, fields in (overrides or {}).items():
        if not isinstance(fields, dict):
            raise ProviderError(f"Provider '{name}' must be a mapping of settings")
        unknown = set(fields) - _PROVIDER_FIELDS
        if unknown:
            raise ProviderError(
                f"Provider '{name}' has unknown settings: {', '.join(sorted(unknown))}"
            )

        if name in providers:
            providers[name] = replace(providers[name], **fields)
            continue

        if not fields.get("base_url"):
            raise ProviderError(f"Custom provider '{name}' needs a base_url")
        settings = dict(fields)
        # A custom provider without any key setting is assumed to be local
        settings.setdefault(
            "requires_key", bool(settings.get("api_key_env") or settings.get("api_key"))
        )
        providers[name] = Provider(name=name, **settings)
    return providers


def configured_provider_names(providers: Dict[str, Provider]) -> List[str]:
    """Names of providers that have the key they need (local ones always count)."""
    return [name for name, p in providers.items() if p.is_configured()]
