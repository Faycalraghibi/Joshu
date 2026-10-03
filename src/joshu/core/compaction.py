"""
Context compaction for the agent loop.

When the conversation nears the model's context window, older turns are replaced
by a model-written summary. Recent turns stay verbatim, and the cut is always
made at a user message so an assistant tool call is never separated from its
tool results.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List

from joshu.core.llm_client import ChatClient

logger = logging.getLogger(__name__)

SUMMARY_PREFIX = "[Summary of the earlier conversation]\n"

SUMMARY_INSTRUCTIONS = """Summarize the conversation below so the work can continue without it.
Keep: the user's goals and constraints, decisions made, files read or changed (with paths), commands run and their important results, errors still open, and what remains to do.
Drop: pleasantries, full file contents, and verbose tool output.
Write it as a compact list of facts."""


def estimate_tokens(messages: List[Dict[str, Any]]) -> int:
    """Rough token count (about 4 characters per token)."""
    total_chars = 0
    for message in messages:
        content = message.get("content") or ""
        total_chars += len(content) if isinstance(content, str) else len(json.dumps(content))
        if message.get("tool_calls"):
            total_chars += len(json.dumps(message["tool_calls"]))
    return total_chars // 4 + 4 * len(messages)


def find_split_index(messages: List[Dict[str, Any]], keep_recent: int) -> int:
    """
    Index where the verbatim tail starts.

    Returns the position of the user message that begins the last `keep_recent`
    user turns, or 0 if there is nothing worth compacting. messages[0] is the
    system prompt and is never part of the compacted range.
    """
    user_indices = [i for i, m in enumerate(messages) if i > 0 and m.get("role") == "user"]
    if len(user_indices) <= keep_recent:
        # A single long turn: cut at the last user message if anything precedes it
        if user_indices and user_indices[-1] > 1:
            return user_indices[-1]
        return 0
    return user_indices[-keep_recent]


def compact_messages(
    messages: List[Dict[str, Any]],
    client: ChatClient,
    keep_recent: int = 2,
    max_summary_tokens: int = 2048,
) -> List[Dict[str, Any]]:
    """
    Replace older turns with a summary.

    Args:
        messages: Full history; messages[0] must be the system prompt
        client: Model used to write the summary
        keep_recent: Number of most recent user turns kept verbatim

    Returns:
        New message list: [system, summary, *recent]. The input is returned
        unchanged when there is nothing to compact.
    """
    split = find_split_index(messages, keep_recent)
    if split <= 1:
        return messages

    old = messages[1:split]
    transcript = _render_transcript(old)

    turn = client.complete(
        [
            {"role": "system", "content": SUMMARY_INSTRUCTIONS},
            {"role": "user", "content": transcript},
        ],
        tools=None,
        max_tokens=max_summary_tokens,
        temperature=0.1,
    )
    summary = turn.content.strip() or "(no summary produced)"
    logger.info(f"Compacted {len(old)} messages into a summary")

    return [messages[0], {"role": "user", "content": SUMMARY_PREFIX + summary}] + messages[split:]


def _render_transcript(messages: List[Dict[str, Any]], tool_output_limit: int = 2000) -> str:
    lines = []
    for message in messages:
        role = message.get("role", "?")
        content = message.get("content") or ""
        if role == "tool" and len(content) > tool_output_limit:
            content = content[:tool_output_limit] + "\n...(truncated)"
        if message.get("tool_calls"):
            calls = ", ".join(
                f"{tc['function']['name']}({tc['function']['arguments']})"
                for tc in message["tool_calls"]
            )
            content = f"{content}\n[tool calls: {calls}]".strip()
        lines.append(f"{role.upper()}: {content}")
    return "\n\n".join(lines)
