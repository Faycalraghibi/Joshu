"""
MCP prompts and resources.

- Prompts become slash commands: `/server:prompt [arguments]` fetches the
  prompt from the server and runs it. Arguments are `key=value` pairs, or plain
  text that fills the prompt's arguments in order (the last one takes the rest).
- Resources are attached with `@server:uri` in a message: the resource's
  content is added for the model.
"""

from __future__ import annotations

import logging
import re
import shlex
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from joshu.mcp.loop import run as run_on_mcp_loop

logger = logging.getLogger(__name__)

MAX_RESOURCE_CHARS = 40_000
# @server:uri — the server must be a configured MCP server (so C:\path isn't one)
_RESOURCE_REF = re.compile(r"(?<![\w@])@([A-Za-z0-9_.-]+):(\S+)")


@dataclass
class PromptInfo:
    server: str
    name: str
    description: str
    arguments: List[Dict[str, Any]]

    @property
    def command(self) -> str:
        return f"{self.server}:{self.name}"


def _run(coro: Any) -> Any:
    """Run an MCP coroutine from synchronous code (as MCP tool calls do)."""
    return run_on_mcp_loop(coro)


def _transports() -> Dict[str, Any]:
    try:
        from joshu.mcp.registry import get_mcp_registry

        return get_mcp_registry().get_connected_transports()
    except Exception:
        return {}


def list_prompts() -> List[PromptInfo]:
    """Prompts offered by the connected MCP servers."""
    found: List[PromptInfo] = []
    for server, transport in _transports().items():
        try:
            prompts = _run(transport.list_prompts())
        except Exception as e:
            logger.debug(f"Listing prompts of {server} failed: {e}")
            continue
        for prompt in prompts or []:
            found.append(
                PromptInfo(
                    server, prompt.name, prompt.description or "", list(prompt.arguments or [])
                )
            )
    return found


def find_prompt(command: str) -> Optional[PromptInfo]:
    """The prompt for `server:name` (with or without a leading slash)."""
    command = command.lstrip("/")
    return next((p for p in list_prompts() if p.command == command), None)


def parse_prompt_arguments(prompt: PromptInfo, text: str) -> Dict[str, str]:
    """`key=value` pairs, or plain words filling the arguments in order."""
    names = [str(a.get("name")) for a in prompt.arguments if a.get("name")]
    text = text.strip()
    if not text or not names:
        return {}
    try:
        words = shlex.split(text)
    except ValueError:
        words = text.split()
    if all("=" in w for w in words):
        return dict(w.split("=", 1) for w in words)
    values: Dict[str, str] = {}
    for index, name in enumerate(names):
        if index >= len(words):
            break
        values[name] = " ".join(words[index:]) if index == len(names) - 1 else words[index]
    return values


def get_prompt_text(prompt: PromptInfo, arguments: Dict[str, str]) -> str:
    """The prompt's text from the server.

    Raises:
        ValueError: a required argument is missing or the server has no text for it.
    """
    missing = [
        str(a["name"])
        for a in prompt.arguments
        if a.get("required") and a.get("name") not in arguments
    ]
    if missing:
        raise ValueError(f"/{prompt.command} needs: {', '.join(missing)}")
    transport = _transports().get(prompt.server)
    if transport is None:
        raise ValueError(f"MCP server '{prompt.server}' is not connected")
    text = _run(transport.get_prompt(prompt.name, arguments))
    if not text:
        raise ValueError(f"/{prompt.command} returned no text")
    return text


def list_resources() -> List[Tuple[str, Any]]:
    """(server, resource definition) for every resource the connected servers list."""
    found = []
    for server, transport in _transports().items():
        try:
            resources = _run(transport.list_resources())
        except Exception as e:
            logger.debug(f"Listing resources of {server} failed: {e}")
            continue
        found.extend((server, resource) for resource in resources or [])
    return found


def expand_resource_refs(text: str) -> Tuple[str, List[str]]:
    """
    Attach `@server:uri` resources: returns the text with each reference
    replaced by `[resource: server:uri]`, plus the attachments to add.
    References to unknown servers are left as they are.
    """
    transports = _transports()
    if not transports or "@" not in text:
        return text, []
    attachments: List[str] = []

    def replace(match: "re.Match[str]") -> str:
        server, raw = match.group(1), match.group(2)
        uri = raw.rstrip(".,;:!?)")
        trailing = raw[len(uri) :]  # punctuation after the reference stays in the text
        transport = transports.get(server)
        if transport is None:
            return match.group(0)
        try:
            content = _run(transport.read_resource(uri))
        except Exception as e:
            attachments.append(f"[Resource {server}:{uri} could not be read: {e}]")
            return f"[resource: {server}:{uri}]{trailing}"
        body = content if isinstance(content, str) else str(content)
        if len(body) > MAX_RESOURCE_CHARS:
            body = body[:MAX_RESOURCE_CHARS] + "\n[... truncated]"
        attachments.append(f"[Resource {server}:{uri}]\n{body}")
        return f"[resource: {server}:{uri}]{trailing}"

    return _RESOURCE_REF.sub(replace, text), attachments


def with_resources(text: str) -> str:
    """The message with its @server:uri resources attached after it."""
    expanded, attachments = expand_resource_refs(text)
    if not attachments:
        return text
    return expanded + "\n\n" + "\n\n".join(attachments)
