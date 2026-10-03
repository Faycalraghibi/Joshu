"""
Prompt-cache breakpoints for providers that need them.

Some models (Anthropic's, through OpenRouter) only reuse a cached prompt
prefix when the request marks where the cacheable prefix ends. The agent's
requests grow by appending, so two breakpoints cover nearly everything: one
after the system prompt (with the tool definitions before it) and one on the
latest user message, so the next request can reuse the whole conversation.

Providers that cache automatically (OpenAI, DeepSeek, Gemini's implicit
caching) need nothing; Anthropic's own OpenAI-compatible endpoint doesn't
support prompt caching.
"""

from __future__ import annotations

import copy
from typing import Any, Dict, List, Sequence

EPHEMERAL = {"type": "ephemeral"}


def model_wants_breakpoints(model: str, patterns: Sequence[str]) -> bool:
    """True when `model` matches one of the provider's patterns ("*" = all)."""
    return any(p == "*" or model.startswith(p) for p in patterns)


def add_cache_breakpoints(messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    A copy of `messages` with cache breakpoints on the system prompt and the
    last user message. The input is not modified.
    """
    marked = list(messages)
    targets = []
    if marked and marked[0].get("role") == "system":
        targets.append(0)
    last_user = next(
        (i for i in range(len(marked) - 1, -1, -1) if marked[i].get("role") == "user"), None
    )
    if last_user is not None and last_user not in targets:
        targets.append(last_user)

    for index in targets:
        marked[index] = _with_breakpoint(marked[index])
    return marked


def _with_breakpoint(message: Dict[str, Any]) -> Dict[str, Any]:
    message = dict(message)
    content = message.get("content")
    if isinstance(content, str):
        if not content:
            return message
        message["content"] = [{"type": "text", "text": content, "cache_control": EPHEMERAL}]
    elif isinstance(content, list) and content:
        parts = copy.deepcopy(content)
        text_parts = [
            part for part in parts if isinstance(part, dict) and part.get("type") == "text"
        ]
        target = text_parts[-1] if text_parts else parts[-1]
        if isinstance(target, dict):
            target["cache_control"] = EPHEMERAL
        message["content"] = parts
    return message
