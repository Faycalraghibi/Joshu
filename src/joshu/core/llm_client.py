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

    def __init__(self, message: str, unreachable: bool = False) -> None:
        """
        Args:
            unreachable: The endpoint could not be reached at all (connection
                error or timeout), so another endpoint may be tried.
        """
        super().__init__(message)
        self.unreachable = unreachable


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
    ) -> AssistantTurn: ...


class OpenAIChatClient:
    """Chat client for OpenAI-compatible APIs."""

    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str,
        extra_headers: Optional[Dict[str, str]] = None,
        timeout: float = 120.0,
    ) -> None:
        from openai import OpenAI

        self.base_url = base_url
        self.model = model
        self.extra_headers = {k: v for k, v in (extra_headers or {}).items() if v}
        import httpx

        # Short connect timeout: an unreachable endpoint should fail fast so the
        # next one can be tried; reads can take long for big responses
        self._client = OpenAI(
            base_url=base_url,
            api_key=api_key,
            timeout=httpx.Timeout(timeout, connect=10.0),
            max_retries=1,
        )

    def complete(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        *,
        max_tokens: int = 4096,
        temperature: float = 0.1,
        on_text: Optional[Callable[[str], None]] = None,
    ) -> AssistantTurn:
        """Run one completion, streaming text to `on_text` when given."""
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

        try:
            if on_text is None:
                return self._complete_blocking(request)
            return self._complete_streaming(request, on_text)
        except LLMError:
            raise
        except Exception as e:
            from openai import APIConnectionError

            # APITimeoutError is a subclass of APIConnectionError
            unreachable = isinstance(e, APIConnectionError)
            raise LLMError(
                f"{self.model} at {self.base_url} request failed: {e}", unreachable=unreachable
            ) from e

    def _complete_blocking(self, request: Dict[str, Any]) -> AssistantTurn:
        completion = self._client.chat.completions.create(**request)
        if not completion.choices:
            raise LLMError(f"{self.model} returned no choices")

        choice = completion.choices[0]
        message = choice.message
        tool_calls = [
            ToolCall(id=tc.id, name=tc.function.name, arguments=tc.function.arguments or "{}")
            for tc in (message.tool_calls or [])
        ]
        return AssistantTurn(
            content=message.content or "",
            tool_calls=tool_calls,
            finish_reason=choice.finish_reason,
            usage=_usage_dict(getattr(completion, "usage", None)),
        )

    def _complete_streaming(
        self, request: Dict[str, Any], on_text: Callable[[str], None]
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


def _usage_dict(usage: Any) -> Dict[str, int]:
    if usage is None:
        return {}
    return {
        "prompt_tokens": getattr(usage, "prompt_tokens", 0) or 0,
        "completion_tokens": getattr(usage, "completion_tokens", 0) or 0,
        "total_tokens": getattr(usage, "total_tokens", 0) or 0,
    }


class FallbackChatClient:
    """
    Tries endpoints in order, moving on when one cannot be reached.

    Only connection failures fall through; a reachable endpoint that rejects the
    request (bad key, bad model) raises immediately. The first endpoint that
    answers becomes the preferred one for later requests.
    """

    def __init__(self, clients: List[OpenAIChatClient]) -> None:
        if not clients:
            raise ValueError("FallbackChatClient needs at least one client")
        self.clients = list(clients)

    @property
    def model(self) -> str:
        return self.clients[0].model

    def complete(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        *,
        max_tokens: int = 4096,
        temperature: float = 0.1,
        on_text: Optional[Callable[[str], None]] = None,
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
                )
            except LLMError as e:
                if not e.unreachable:
                    raise
                logger.warning(f"Endpoint unreachable, trying the next one: {e}")
                failures.append(str(e))
                continue
            if index:
                self.clients.insert(0, self.clients.pop(index))
            return turn

        raise LLMError(
            "No configured model endpoint could be reached:\n- " + "\n- ".join(failures),
            unreachable=True,
        )


def create_chat_client(model: Optional[str] = None, provider: Optional[str] = None) -> ChatClient:
    """
    Build the chat client for the configured provider.

    The provider comes from `provider` or the `provider` config value; the model
    from `model`, else the `model` config value (when using the configured
    provider), else the provider's default. Providers listed in
    `fallback_providers` are tried, with their default models, when the main
    one can't be reached.

    Raises:
        LLMError: for an unknown provider, a missing API key, or no model.
    """
    from joshu.core.config import get_config_manager
    from joshu.core.providers import DEFAULT_PROVIDER, ProviderError, get_providers

    config = get_config_manager()
    configured = config.get("provider") or DEFAULT_PROVIDER
    name = provider or configured
    if name == configured:
        model = model or config.get("model")

    try:
        providers = get_providers(config.get("providers") or {})
    except ProviderError as e:
        raise LLMError(f"Invalid provider configuration: {e}") from e

    if name not in providers:
        raise LLMError(
            f"Unknown provider '{name}'. Known providers: {', '.join(sorted(providers))}. "
            "Add custom ones under `providers:` in config.yaml."
        )

    clients = [_client_for_provider(providers[name], model)]
    for fallback in config.get("fallback_providers") or []:
        if fallback == name or fallback not in providers:
            continue
        try:
            clients.append(_client_for_provider(providers[fallback], None))
        except LLMError as e:
            logger.debug(f"Skipping fallback provider {fallback}: {e}")

    return clients[0] if len(clients) == 1 else FallbackChatClient(clients)


def _client_for_provider(provider: Any, model: Optional[str]) -> OpenAIChatClient:
    """OpenAI-compatible client for one provider."""
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
    )
