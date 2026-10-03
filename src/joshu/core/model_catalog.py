"""
Models: what a provider serves, and your own named models.

Model lists come live from the provider's OpenAI-compatible `GET /models`
endpoint, so new models show up without a Joshu update. OpenRouter also says
which models support tool calling, which are free and their context size.

Named models (the `models` setting) give a model a short name and optional
settings:

    models:
      fast:
        provider: nvidia
        model: nvidia/nemotron-3.5-lightning-30b-a3b
        context_window: 128000

`--model fast`, `joshu use fast` and `/model fast` then pick that provider
and model.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)

LIST_TIMEOUT = 30.0


class CatalogError(Exception):
    """A provider's model list couldn't be fetched."""


@dataclass
class ModelInfo:
    id: str
    context_length: Optional[int] = None
    tools: Optional[bool] = None  # None: the provider doesn't say
    free: Optional[bool] = None


@dataclass
class NamedModel:
    name: str
    provider: str
    model: str
    context_window: Optional[int] = None


def list_models(provider: Any) -> List[ModelInfo]:
    """
    Models served by `provider` (a joshu.core.providers.Provider), sorted by id.

    Raises:
        CatalogError: the endpoint couldn't be reached or returned no list.
    """
    url = provider.base_url.rstrip("/") + "/models"
    headers = {}
    key = provider.resolve_api_key()
    if key:
        headers["Authorization"] = f"Bearer {key}"
    try:
        response = httpx.get(url, headers=headers, timeout=LIST_TIMEOUT)
        response.raise_for_status()
        data = response.json()
    except (httpx.HTTPError, ValueError) as e:
        raise CatalogError(f"Could not list models from {provider.name} ({url}): {e}") from e

    entries = data.get("data") if isinstance(data, dict) else data
    if not isinstance(entries, list):
        raise CatalogError(f"{provider.name} returned no model list from {url}")
    models = [
        _model_info(entry) for entry in entries if isinstance(entry, dict) and entry.get("id")
    ]
    return sorted(models, key=lambda m: m.id)


def _model_info(entry: Dict[str, Any]) -> ModelInfo:
    parameters = entry.get("supported_parameters")
    pricing = entry.get("pricing") or {}
    free = None
    if isinstance(pricing, dict) and pricing:
        try:
            free = float(pricing.get("prompt", 1)) == 0 and float(pricing.get("completion", 1)) == 0
        except (TypeError, ValueError):
            free = None
    context = entry.get("context_length")
    return ModelInfo(
        id=str(entry["id"]),
        context_length=context if isinstance(context, int) else None,
        tools=("tools" in parameters) if isinstance(parameters, list) else None,
        free=free,
    )


def filter_models(
    models: List[ModelInfo],
    search: Optional[str] = None,
    tools_only: bool = False,
    free_only: bool = False,
) -> List[ModelInfo]:
    terms = [t.lower() for t in (search or "").split()]
    result = []
    for model in models:
        if terms and not all(t in model.id.lower() for t in terms):
            continue
        if tools_only and model.tools is False:
            continue
        if free_only and model.free is False:
            continue
        result.append(model)
    return result


def named_models(config_value: Optional[Dict[str, Any]]) -> Dict[str, NamedModel]:
    """Parse the `models` setting; malformed entries are skipped with a warning."""
    result: Dict[str, NamedModel] = {}
    for name, entry in (config_value or {}).items():
        if not isinstance(entry, dict) or not entry.get("model") or not entry.get("provider"):
            logger.warning(f"models.{name} needs a provider and a model")
            continue
        window = entry.get("context_window")
        result[str(name)] = NamedModel(
            name=str(name),
            provider=str(entry["provider"]),
            model=str(entry["model"]),
            context_window=window if isinstance(window, int) and window > 0 else None,
        )
    return result


def resolve_named_model(name: Optional[str]) -> Optional[NamedModel]:
    """The named model called `name`, if there is one."""
    if not name:
        return None
    from joshu.core.config import get_config_manager

    return named_models(get_config_manager().get("models")).get(name)


@dataclass
class CheckResult:
    ok: bool
    tool_call: bool = False
    seconds: float = 0.0
    error: str = ""


_PING_TOOL = {
    "type": "function",
    "function": {
        "name": "ping",
        "description": "Reply to a ping. Always call this when asked to ping.",
        "parameters": {"type": "object", "properties": {}},
    },
}


def check_model(provider: Any, model: str, timeout: float = 60.0) -> CheckResult:
    """
    Send one small request with a tool to see whether the model answers and
    calls tools. Catches models a provider lists but the account can't use.
    """
    import time

    from joshu.core.llm_client import LLMError, _client_for_provider

    start = time.monotonic()
    try:
        client = _client_for_provider(provider, model, timeout=timeout, retries=2)
        turn = client.complete(
            [{"role": "user", "content": "Call the ping tool."}],
            [_PING_TOOL],
            max_tokens=512,
            temperature=0,
        )
    except LLMError as e:
        return CheckResult(ok=False, seconds=time.monotonic() - start, error=str(e))
    return CheckResult(
        ok=True,
        tool_call=any(c.name == "ping" for c in turn.tool_calls),
        seconds=time.monotonic() - start,
    )
