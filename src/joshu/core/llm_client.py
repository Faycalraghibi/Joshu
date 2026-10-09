"""
Chat client with native tool calling for the agent loop.

Talks to any OpenAI-compatible endpoint (vLLM server, local model API, OpenRouter),
streams text and tool-call deltas, and raises LLMError with an actionable message
instead of swallowing failures.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Protocol

logger = logging.getLogger(__name__)


class LLMError(Exception):
    """Raised when the model endpoint is missing or a request fails."""

    def __init__(self, message: str, unreachable: bool = False, unavailable: bool = False) -> None:
        """
        Args:
            unreachable: The endpoint could not be reached at all (connection
                error or timeout).
            unavailable: The endpoint answered but can't serve the request
                right now or at all (unknown model, rate limit, server error).
                Either way another endpoint may be tried.
        """
        super().__init__(message)
        self.unreachable = unreachable
        self.unavailable = unavailable or unreachable


# Status codes after which another model may succeed: unknown model (some
# providers list models an account can't call), timeout, rate limit, server error
FAILOVER_STATUS = {404, 408, 409, 429, 500, 502, 503, 504}

DEFAULT_REQUEST_TIMEOUT = 120.0
DEFAULT_REQUEST_RETRIES = 3


@dataclass
class ToolCall:
    """A tool call requested by the model."""

    id: str
    name: str
    arguments: str  # JSON-encoded, as returned by the API

    def parsed_arguments(self) -> Dict[str, Any]:
        """Decode the arguments JSON; raises ValueError on malformed input."""
        if not self.arguments or not self.arguments.strip():
            return {}
        value = json.loads(self.arguments)
        if not isinstance(value, dict):
            raise ValueError("tool arguments must be a JSON object")
        return value

    def to_message_dict(self) -> Dict[str, Any]:
        """Format for an assistant message's `tool_calls` list."""
        return {
            "id": self.id,
            "type": "function",
            "function": {"name": self.name, "arguments": self.arguments or "{}"},
        }


@dataclass
class AssistantTurn:
    """One model response: text, tool calls, and usage."""

    content: str = ""
    tool_calls: List[ToolCall] = field(default_factory=list)
    finish_reason: Optional[str] = None
    usage: Dict[str, int] = field(default_factory=dict)

    def to_message_dict(self) -> Dict[str, Any]:
        """Format as an assistant message for the conversation history."""
        message: Dict[str, Any] = {"role": "assistant", "content": self.content or ""}
        if self.tool_calls:
            message["tool_calls"] = [tc.to_message_dict() for tc in self.tool_calls]
        return message


class ChatClient(Protocol):
    """Anything that can run one chat completion with tools."""

    model: str

    def complete(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        *,
        max_tokens: int = 4096,
        temperature: float = 0.1,
        on_text: Optional[Callable[[str], None]] = None,
        on_reasoning: Optional[Callable[[str], None]] = None,
    ) -> AssistantTurn:
        """Run one completion; stream text to `on_text` when given, and the
        model's reasoning (from models that expose it) to `on_reasoning`."""


class OpenAIChatClient:
    """Chat client for OpenAI-compatible APIs."""

    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str,
        extra_headers: Optional[Dict[str, str]] = None,
        extra_body: Optional[Dict[str, Any]] = None,
        no_thinking_options: Optional[Dict[str, Any]] = None,
        cache_breakpoints: bool = False,
        timeout: float = DEFAULT_REQUEST_TIMEOUT,
        max_retries: int = DEFAULT_REQUEST_RETRIES,
    ) -> None:
        from openai import OpenAI

        self.base_url = base_url
        self.model = model
        self.extra_headers = {k: v for k, v in (extra_headers or {}).items() if v}
        # Provider-specific request fields, e.g. OpenRouter's usage accounting
        self.extra_body = dict(extra_body or {})
        # Fields that turn thinking off for a request (complete(thinking=False))
        self.no_thinking_options = dict(no_thinking_options or {})
        # Mark the cacheable prompt prefix (see joshu.core.prompt_cache)
        self.cache_breakpoints = cache_breakpoints
        # Context size of the model, when known (named models can set it)
        self.context_window: Optional[int] = None
        import httpx

        # Short connect timeout: an unreachable endpoint should fail fast so the
        # next one can be tried; reads can take long for big responses. The SDK
        # retries connection errors, 408/409/429 and 5xx with exponential
        # backoff, honoring Retry-After.
        self._client = OpenAI(
            base_url=base_url,
            api_key=api_key,
            timeout=httpx.Timeout(timeout, connect=10.0),
            max_retries=max(0, max_retries),
        )

    def complete(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        *,
        max_tokens: int = 4096,
        temperature: float = 0.1,
        on_text: Optional[Callable[[str], None]] = None,
        on_reasoning: Optional[Callable[[str], None]] = None,
        thinking: Optional[bool] = None,
    ) -> AssistantTurn:
        """
        Run one completion (always streamed), passing text to `on_text` when given.
        `thinking=False` asks a reasoning model not to think first, where the
        provider has a switch for it (no_thinking_options).
        """
        if self.cache_breakpoints:
            from joshu.core.prompt_cache import add_cache_breakpoints

            messages = add_cache_breakpoints(messages)
        request: Dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if tools:
            request["tools"] = tools
        if self.extra_headers:
            request["extra_headers"] = self.extra_headers
        extra_body = dict(self.extra_body)
        if thinking is False and self.no_thinking_options:
            extra_body = _merged(extra_body, self.no_thinking_options)
        if extra_body:
            request["extra_body"] = extra_body

        try:
            # Streamed even when nothing is shown (joshu run, -p, the SDK): the
            # timeout then applies to each chunk rather than the whole answer,
            # so a model that thinks for minutes before answering isn't cut off
            return self._complete_streaming(request, on_text or _ignore, on_reasoning)
        except LLMError:
            raise
        except Exception as e:
            from openai import APIConnectionError, APIStatusError

            # APITimeoutError is a subclass of APIConnectionError
            unreachable = isinstance(e, APIConnectionError)
            unavailable = isinstance(e, APIStatusError) and e.status_code in FAILOVER_STATUS
            raise LLMError(
                f"{self.model} at {self.base_url} request failed: {_describe_error(e)}",
                unreachable=unreachable,
                unavailable=unavailable,
            ) from e

    def _complete_streaming(
        self,
        request: Dict[str, Any],
        on_text: Callable[[str], None],
        on_reasoning: Optional[Callable[[str], None]] = None,
    ) -> AssistantTurn:
        stream = self._client.chat.completions.create(
            **request, stream=True, stream_options={"include_usage": True}
        )

        text_parts: List[str] = []
        calls: Dict[int, Dict[str, str]] = {}
        finish_reason: Optional[str] = None
        usage: Dict[str, int] = {}

        for chunk in stream:
            if getattr(chunk, "usage", None):
                usage = _usage_dict(chunk.usage)
            if not chunk.choices:
                continue

            choice = chunk.choices[0]
            delta = choice.delta
            if choice.finish_reason:
                finish_reason = choice.finish_reason

            if delta is None:
                continue

            if on_reasoning is not None:
                thought = _reasoning_delta(delta)
                if thought:
                    on_reasoning(thought)

            if delta.content:
                text_parts.append(delta.content)
                on_text(delta.content)

            # Tool call arguments arrive in fragments keyed by index
            for tc in delta.tool_calls or []:
                slot = calls.setdefault(tc.index, {"id": "", "name": "", "arguments": ""})
                if tc.id:
                    slot["id"] = tc.id
                if tc.function is not None:
                    if tc.function.name:
                        slot["name"] += tc.function.name
                    if tc.function.arguments:
                        slot["arguments"] += tc.function.arguments

        tool_calls = [
            ToolCall(
                id=slot["id"] or f"call_{index}",
                name=slot["name"],
                arguments=slot["arguments"] or "{}",
            )
            for index, slot in sorted(calls.items())
            if slot["name"]
        ]
        return AssistantTurn(
            content="".join(text_parts),
            tool_calls=tool_calls,
            finish_reason=finish_reason,
            usage=usage,
        )


def _ignore(_text: str) -> None:
    pass


def _merged(base: Dict[str, Any], extra: Dict[str, Any]) -> Dict[str, Any]:
    """`base` with `extra` laid over it, merging nested mappings."""
    merged = dict(base)
    for key, value in extra.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _merged(merged[key], value)
        else:
            merged[key] = value
    return merged


def _describe_error(error: Exception) -> str:
    """
    A short, readable reason for a failed request: the HTTP status and the
    provider's message. The raw error body is left out; it can be long and
    carry account metadata (user ids, rate-limit headers).
    """
    status = getattr(error, "status_code", None)
    if status is None:
        return str(error)
    body = getattr(error, "body", None)
    message = ""
    if isinstance(body, dict):
        inner = body.get("error") if isinstance(body.get("error"), dict) else body
        message = str(inner.get("message") or "")
    message = " ".join((message or getattr(error, "message", "") or "").split())
    if len(message) > 300:
        message = message[:297] + "..."
    label = {401: "unauthorized (check the API key)", 429: "rate limited"}.get(status, "")
    head = f"HTTP {status}" + (f" {label}" if label else "")
    return f"{head}: {message}" if message else head


def _reasoning_delta(delta: Any) -> str:
    """Reasoning text in a streamed delta: `reasoning_content` (DeepSeek, NVIDIA,
    vLLM) or `reasoning` (OpenRouter and others); empty when there is none."""
    for name in ("reasoning_content", "reasoning"):
        value = getattr(delta, name, None)
        if value is None:
            value = (getattr(delta, "model_extra", None) or {}).get(name)
        if isinstance(value, str) and value:
            return value
    return ""


def _usage_dict(usage: Any) -> Dict[str, Any]:
    if usage is None:
        return {}
    result: Dict[str, Any] = {
        "prompt_tokens": getattr(usage, "prompt_tokens", 0) or 0,
        "completion_tokens": getattr(usage, "completion_tokens", 0) or 0,
        "total_tokens": getattr(usage, "total_tokens", 0) or 0,
    }
    # Providers that report cost (OpenRouter) add it as an extra usage field
    cost = getattr(usage, "cost", None)
    if cost is None:
        cost = (getattr(usage, "model_extra", None) or {}).get("cost")
    if isinstance(cost, (int, float)) and not isinstance(cost, bool):
        result["cost"] = float(cost)
    # Input tokens served from the provider's prompt cache
    details = getattr(usage, "prompt_tokens_details", None)
    cached = getattr(details, "cached_tokens", None) if details is not None else None
    if isinstance(details, dict):
        cached = details.get("cached_tokens")
    if isinstance(cached, int) and cached > 0:
        result["cached_tokens"] = cached
    return result


class FallbackChatClient:
    """
    Tries endpoints in order, moving on when one can't serve the request.

    Connection failures, timeouts, unknown models, rate limits and server errors
    (after the client's own retries) fall through to the next endpoint; other
    rejections (bad key, invalid request) raise immediately. The first endpoint
    that answers becomes the preferred one for later requests.
    """

    def __init__(self, clients: List[OpenAIChatClient]) -> None:
        if not clients:
            raise ValueError("FallbackChatClient needs at least one client")
        self.clients = list(clients)

    @property
    def model(self) -> str:
        return self.clients[0].model

    @property
    def context_window(self) -> Optional[int]:
        return getattr(self.clients[0], "context_window", None)

    def complete(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        *,
        max_tokens: int = 4096,
        temperature: float = 0.1,
        on_text: Optional[Callable[[str], None]] = None,
        on_reasoning: Optional[Callable[[str], None]] = None,
    ) -> AssistantTurn:
        failures = []
        for index, client in enumerate(self.clients):
            try:
                turn = client.complete(
                    messages,
                    tools,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    on_text=on_text,
                    on_reasoning=on_reasoning,
                )
            except LLMError as e:
                if not e.unavailable:
                    raise
                logger.warning(f"Endpoint unavailable, trying the next one: {e}")
                failures.append(str(e))
                continue
            if index:
                self.clients.insert(0, self.clients.pop(index))
            return turn

        raise LLMError(
            "No configured model could serve the request:\n- " + "\n- ".join(failures),
            unavailable=True,
        )


def create_chat_client(model: Optional[str] = None, provider: Optional[str] = None) -> ChatClient:
    """
    Build the chat client for the configured provider.

    The provider comes from `provider` or the `provider` config value; the model
    from `model`, else the `model` config value (when using the configured
    provider), else the provider's default. Entries of `fallback_providers`
    (provider names, which use their default model, or named models) are tried
    in order when the main model can't serve a request.

    Raises:
        LLMError: for an unknown provider, a missing API key, or no model.
    """
    from joshu.core.config import get_config_manager
    from joshu.core.model_catalog import resolve_named_model
    from joshu.core.providers import DEFAULT_PROVIDER, ProviderError, get_providers

    config = get_config_manager()
    configured = config.get("provider") or DEFAULT_PROVIDER
    name = provider or configured
    if name == configured:
        model = model or config.get("model")

    # A named model (the `models` setting) brings its own provider and settings
    named = resolve_named_model(model)
    if named is not None:
        name, model = named.provider, named.model

    try:
        providers = get_providers(config.get("providers") or {})
    except ProviderError as e:
        raise LLMError(f"Invalid provider configuration: {e}") from e

    if name not in providers:
        raise LLMError(
            f"Unknown provider '{name}'. Known providers: {', '.join(sorted(providers))}. "
            "Add custom ones under `providers:` in config.yaml."
        )

    timeout = _number(config.get("request_timeout"), DEFAULT_REQUEST_TIMEOUT)
    retries = int(_number(config.get("request_retries"), DEFAULT_REQUEST_RETRIES))

    clients = [_client_for_provider(providers[name], model, timeout, retries)]
    if named is not None and named.context_window:
        clients[0].context_window = named.context_window
    for fallback in config.get("fallback_providers") or []:
        fallback_named = resolve_named_model(fallback)
        if fallback_named is not None:
            target, target_model = fallback_named.provider, fallback_named.model
        else:
            target, target_model = fallback, None
        if target not in providers:
            logger.debug(f"Skipping fallback {fallback}: unknown provider {target}")
            continue
        try:
            client = _client_for_provider(providers[target], target_model, timeout, retries)
        except LLMError as e:
            logger.debug(f"Skipping fallback {fallback}: {e}")
            continue
        if (client.base_url, client.model) == (clients[0].base_url, clients[0].model):
            continue
        if fallback_named is not None and fallback_named.context_window:
            client.context_window = fallback_named.context_window
        clients.append(client)

    return clients[0] if len(clients) == 1 else FallbackChatClient(clients)


def _number(value: Any, default: float) -> float:
    if isinstance(value, (int, float)) and not isinstance(value, bool) and value >= 0:
        return float(value)
    return default


def _client_for_provider(
    provider: Any,
    model: Optional[str],
    timeout: float = DEFAULT_REQUEST_TIMEOUT,
    retries: int = DEFAULT_REQUEST_RETRIES,
) -> OpenAIChatClient:
    """OpenAI-compatible client for one provider."""
    from joshu.core.prompt_cache import model_wants_breakpoints

    model = model or provider.default_model
    if not model:
        raise LLMError(
            f"No model set for provider '{provider.name}'. "
            "Pass --model or set `model` in config.yaml."
        )

    api_key = provider.resolve_api_key()
    if provider.requires_key and not api_key:
        where = f"set {provider.api_key_env}" if provider.api_key_env else "set api_key"
        raise LLMError(f"Provider '{provider.name}' needs an API key: {where}.")

    return OpenAIChatClient(
        base_url=provider.base_url,
        api_key=api_key or "not-needed",
        model=model,
        extra_headers=dict(provider.headers),
        extra_body=dict(provider.request_options),
        no_thinking_options=dict(provider.no_thinking_options),
        cache_breakpoints=model_wants_breakpoints(model, provider.cache_control_models),
        timeout=timeout or DEFAULT_REQUEST_TIMEOUT,
        max_retries=retries,
    )
