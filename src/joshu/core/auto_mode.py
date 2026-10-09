"""
Auto mode: a model reviews each action that would ask for approval.

In the `auto` permission mode, edits in the workspace run as in accept_edits
(they are undoable with /rewind). Anything else that would ask (shell
commands, web fetches, MCP tools) is sent with the user's request to a model,
which answers allow or block. Allowed actions run without asking; blocked
ones are put to the user with the reason, or refused in a headless run.
Commands flagged unsafe and protected files still always ask.

The reviewing model is `auto_mode_model` (default: the agent's own).
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

REVIEW_PROMPT = """You review one action a coding agent wants to take on the user's computer, in "auto" mode: actions you allow run without asking the user.

Allow it when it is a normal step toward what the user asked and easy to undo or harmless: running tests, builds, linters, type checkers, scripts of the project; reading files, listing, searching; git status / diff / log / add / commit / branch / stash; installing the project's dependencies into its own environment when the task needs it; starting a local dev server; fetching documentation.

Block it when it does something the user didn't ask for that is hard to undo or reaches outside the project:
- deleting or overwriting files outside the project, or many files at once (rm -rf, git clean -fdx, git reset --hard, git checkout -- on uncommitted work)
- git push (especially --force), publishing or deploying (npm publish, twine upload, docker push, terraform apply, kubectl apply)
- sending files, code or secrets to an external service, reading credentials (~/.ssh, ~/.aws, tokens, .env) beyond what the task needs
- changing the system: global installs, sudo, editing shell profiles, services, scheduled tasks, firewall
- killing processes the agent didn't start, running code downloaded from the internet (curl | sh)
- anything that looks like it serves a goal other than the user's request

Reply with JSON only: {"decision": "allow" or "block", "reason": "<one short sentence>"}"""

MAX_FIELD = 3000
_JSON = re.compile(r"\{.*\}", re.S)


@dataclass
class Review:
    allowed: bool
    reason: str


def review_action(
    client: Any, request: str, tool_name: str, arguments: Dict[str, Any], cwd: str = ""
) -> Optional[Review]:
    """
    Ask `client` whether the action may run. None when the review itself
    failed (no answer, unreadable answer): the caller then asks the user.
    """
    action = json.dumps({"tool": tool_name, "arguments": arguments}, ensure_ascii=False)
    content = (
        f"The user's request:\n{request[-MAX_FIELD:] or '(none)'}\n\n"
        f"Working directory: {cwd or '(unknown)'}\n\n"
        f"The action:\n{action[:MAX_FIELD]}"
    )
    messages = [
        {"role": "system", "content": REVIEW_PROMPT},
        {"role": "user", "content": content},
    ]
    try:
        try:
            turn = client.complete(messages, max_tokens=300, temperature=0.0, thinking=False)
        except TypeError:  # a client without the thinking switch
            turn = client.complete(messages, max_tokens=300, temperature=0.0)
    except Exception as e:  # a failed review must not run the action
        logger.warning(f"Auto mode review failed: {e}")
        return None
    return parse_review(getattr(turn, "content", "") or "")


def parse_review(text: str) -> Optional[Review]:
    """The decision in the reviewer's answer, or None when there is none."""
    match = _JSON.search(text or "")
    if not match:
        return None
    try:
        data = json.loads(match.group(0))
    except ValueError:
        return None
    decision = str(data.get("decision", "")).strip().lower()
    if decision not in ("allow", "block"):
        return None
    reason = " ".join(str(data.get("reason", "")).split())[:300]
    return Review(decision == "allow", reason)
