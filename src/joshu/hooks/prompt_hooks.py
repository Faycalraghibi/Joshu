"""
Prompt hooks: a model decides instead of a script.

A hook entry with `prompt` (or a Claude Code hook of type "prompt") sends the
prompt and the event (as JSON, in place of `$ARGUMENTS`, or after the prompt)
to a model, which answers {"ok": true} or {"ok": false, "reason": "..."}.
`ok: false` blocks the event like a script exiting with code 2; for `stop`,
it sends the agent back to work with the reason. The model is `hook_model`,
or the configured one. If it can't be reached or answers something else, the
event goes ahead (and the problem is logged), as with a failing script hook.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Optional

from joshu.hooks.schemas import HookResponse, HookResult

logger = logging.getLogger(__name__)

SYSTEM = (
    "You are a hook in a coding agent: you decide whether an event may go ahead. "
    "Follow the instructions, judge the event (JSON), and reply with JSON only: "
    '{"ok": true} to let it go ahead, or {"ok": false, "reason": "..."} to stop it, '
    "with a short reason the agent can act on."
)
_client: Any = None


def _hook_client() -> Any:
    global _client
    if _client is None:
        from joshu.core.config import get_config_manager
        from joshu.core.llm_client import create_chat_client

        model = str(get_config_manager().get("hook_model", "") or "") or None
        _client = create_chat_client(model)
    return _client


def reset() -> None:
    """Forget the client (tests, or after the model setting changes)."""
    global _client
    _client = None


def decision(text: str) -> Optional[dict]:
    """The {"ok": ...} object in a model's reply, or None."""
    match = re.search(r"\{.*\}", text or "", re.S)
    if not match:
        return None
    try:
        data = json.loads(match.group(0))
    except ValueError:
        return None
    return data if isinstance(data, dict) and "ok" in data else None


def run_prompt_hook(prompt: str, event_json: str, timeout: Optional[int] = None) -> HookResult:
    instructions = (
        prompt.replace("$ARGUMENTS", event_json)
        if "$ARGUMENTS" in prompt
        else f"{prompt}\n\nEvent:\n{event_json}"
    )
    try:
        turn = _hook_client().complete(
            [{"role": "system", "content": SYSTEM}, {"role": "user", "content": instructions}],
            max_tokens=400,
            temperature=0.0,
        )
    except Exception as e:  # an unreachable model must not stop the agent
        logger.warning(f"Prompt hook couldn't ask the model: {e}")
        return HookResult(success=False, allowed=True, error=str(e))
    answer = decision(turn.content or "")
    if answer is None:
        logger.warning(f"Prompt hook got no decision: {(turn.content or '')[:120]!r}")
        return HookResult(success=False, allowed=True, error="no decision in the reply")
    if answer.get("ok") is False:
        reason = str(answer.get("reason") or "A prompt hook stopped this.")
        return HookResult(
            success=True, allowed=False, response=HookResponse(action="block", message=reason)
        )
    return HookResult(success=True, allowed=True)
