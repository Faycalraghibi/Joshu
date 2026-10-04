"""
Tools whose definitions are only sent to the model once it asks for them.

Every tool definition is sent with every request, so a few MCP servers can
cost thousands of tokens per request even when none of their tools is used
(34 GitHub and TestSprite tools measured at ~5k tokens per request). Large MCP
tool sets are therefore deferred: the system prompt lists their names, and the
`load_tools` tool sends the full definitions of the ones the model needs,
which then stay available for the rest of the session.

The `defer_mcp_tools` setting: "auto" (default; defer when MCP definitions
would cost more than DEFER_THRESHOLD tokens per request), true, or false.
"""

from __future__ import annotations

import json
from typing import Any, Dict, Iterable, List, Optional

from joshu.core.tool_registry import ToolSpec

DEFER_THRESHOLD = 1500  # estimated tokens of MCP tool definitions per request
LOAD_TOOLS = "load_tools"


def server_of(spec: ToolSpec) -> Optional[str]:
    """The MCP server a tool comes from, or None for other tools."""
    definition = getattr(spec.function, "definition", None)
    server = getattr(definition, "server_name", None)
    return str(server) if server else None


def estimate_tokens(specs: Iterable[ToolSpec]) -> int:
    return sum(len(json.dumps(spec.to_openai_format())) for spec in specs) // 4


def should_defer(mode: Any, mcp_specs: List[ToolSpec]) -> bool:
    if not mcp_specs:
        return False
    if isinstance(mode, bool):
        return mode
    value = str(mode).strip().lower()
    if value in ("true", "always", "yes", "on"):
        return True
    if value in ("false", "never", "no", "off"):
        return False
    return estimate_tokens(mcp_specs) > DEFER_THRESHOLD


def index_prompt(specs: List[ToolSpec]) -> str:
    """System prompt section listing deferred tools by server."""
    by_server: Dict[str, List[str]] = {}
    for spec in specs:
        by_server.setdefault(server_of(spec) or "other", []).append(spec.name)
    lines = [
        "More tools are available but not loaded, to keep requests small. To use one, "
        f"first call `{LOAD_TOOLS}` with its name (or a search word); it then stays "
        "available for the rest of the session."
    ]
    for server, names in sorted(by_server.items()):
        lines.append(f"- {server}: {', '.join(sorted(names))}")
    return "\n".join(lines)


def match(specs: List[ToolSpec], names: Iterable[str], query: str = "") -> List[ToolSpec]:
    """Deferred tools matching exact names, or a search over names and descriptions."""
    wanted = {str(n).strip() for n in names if str(n).strip()}
    found = [spec for spec in specs if spec.name in wanted]
    words = [w for w in query.lower().split() if w]
    if words:
        for spec in specs:
            text = f"{spec.name} {server_of(spec) or ''} {spec.description}".lower()
            if spec not in found and all(w in text for w in words):
                found.append(spec)
    return found


LOAD_TOOLS_DESCRIPTION = (
    "Load tools listed under 'More tools' in the system prompt so you can call them. "
    "Pass exact `names`, or a `query` to search names and descriptions."
)

LOAD_TOOLS_PARAMETERS = {
    "type": "object",
    "properties": {
        "names": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Tool names to load",
        },
        "query": {"type": "string", "description": "Search words, e.g. 'github issue'"},
    },
}
