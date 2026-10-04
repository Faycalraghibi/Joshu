"""
Clearing old tool results: the cheapest way to keep a long session small.

Every tool result stays in the conversation and is re-sent with every later
request. A session that reads 15 files carries all of them on every request,
long after the model used them. When the conversation grows past
`clear_tool_results_at` tokens, the outputs of all but the most recent tool
calls are replaced with a one-line note saying how to get them back (call the
tool again), and so are large arguments of old write_file calls.

Clearing changes earlier messages, so the provider's prompt cache has to be
rebuilt once; it therefore happens in batches, only when it frees at least
MIN_FREED_TOKENS, rather than a little on every turn. Summarizing
(compaction) remains the last resort when clearing isn't enough.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Tuple

CLEARED_PREFIX = "[Cleared to save context"
KEEP_RECENT = 6  # tool results always kept in full
MIN_CLEAR_CHARS = 400  # results smaller than this aren't worth clearing
MIN_FREED_TOKENS = 5000  # don't rebuild the cache for less
# Results that stay useful for the whole session
NEVER_CLEAR = {"skill", "task", "load_tools", "memory", "write_todos"}
# Large arguments of old edit calls that can be cleared too
CLEARABLE_ARGUMENTS = {"write_file": ("content",)}


def clear_old_tool_results(
    messages: List[Dict[str, Any]], keep_recent: int = KEEP_RECENT
) -> Tuple[List[Dict[str, Any]], int, int]:
    """
    A copy of `messages` with old tool results (and large old write_file
    contents) replaced by short notes.

    Returns:
        (new messages, number of items cleared, estimated tokens freed).
        The input is returned unchanged when less than MIN_FREED_TOKENS would
        be freed.
    """
    calls: Dict[str, Tuple[str, Dict[str, Any]]] = {}
    for message in messages:
        for call in message.get("tool_calls") or []:
            function = call.get("function") or {}
            try:
                arguments = json.loads(function.get("arguments") or "{}")
            except ValueError:
                arguments = {}
            calls[call.get("id", "")] = (
                function.get("name", ""),
                arguments if isinstance(arguments, dict) else {},
            )

    tool_indices = [i for i, m in enumerate(messages) if m.get("role") == "tool"]
    if len(tool_indices) <= keep_recent:
        return messages, 0, 0
    cutoff = tool_indices[-keep_recent] if keep_recent else len(messages)

    edited = list(messages)
    cleared = 0
    freed_chars = 0
    for index in tool_indices:
        if index >= cutoff:
            break
        message = messages[index]
        content = str(message.get("content") or "")
        name, arguments = calls.get(message.get("tool_call_id", ""), ("", {}))
        if (
            name in NEVER_CLEAR
            or len(content) < MIN_CLEAR_CHARS
            or content.startswith(CLEARED_PREFIX)
        ):
            continue
        note = f"{CLEARED_PREFIX}: output of {describe_call(name, arguments)}. Call it again if you need it.]"
        edited[index] = {**message, "content": note}
        cleared += 1
        freed_chars += len(content) - len(note)

    # Large contents written by old write_file calls
    for index in range(1, cutoff):
        message = edited[index]
        if message.get("role") != "assistant" or not message.get("tool_calls"):
            continue
        new_calls = []
        changed = False
        for call in message["tool_calls"]:
            function = call.get("function") or {}
            keys = CLEARABLE_ARGUMENTS.get(function.get("name", ""))
            raw = function.get("arguments") or ""
            if keys and len(raw) >= MIN_CLEAR_CHARS:
                try:
                    arguments = json.loads(raw)
                except ValueError:
                    arguments = None
                if isinstance(arguments, dict):
                    for key in keys:
                        value = arguments.get(key)
                        if isinstance(value, str) and len(value) >= MIN_CLEAR_CHARS:
                            arguments[key] = f"{CLEARED_PREFIX}: {len(value)} characters written]"
                    new_raw = json.dumps(arguments, ensure_ascii=False)
                    if len(new_raw) < len(raw):
                        freed_chars += len(raw) - len(new_raw)
                        call = {**call, "function": {**function, "arguments": new_raw}}
                        changed = True
                        cleared += 1
            new_calls.append(call)
        if changed:
            edited[index] = {**message, "tool_calls": new_calls}

    freed = freed_chars // 4
    if freed < MIN_FREED_TOKENS:
        return messages, 0, 0
    return edited, cleared, freed


def describe_call(name: str, arguments: Dict[str, Any]) -> str:
    """`read_file(path=calc.py)`-style description of a call, kept short."""
    if not name:
        return "a tool call"
    parts = []
    for key, value in arguments.items():
        text = " ".join(str(value).split())
        if len(text) > 60:
            text = text[:57] + "..."
        parts.append(f"{key}={text}")
        if len(parts) == 3:
            break
    return f"{name}({', '.join(parts)})"
