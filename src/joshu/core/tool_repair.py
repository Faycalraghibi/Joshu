"""
Recovering tool calls that weaker models get slightly wrong.

Open and small models often send tool arguments that aren't quite JSON
(code fences, trailing commas, Python literals, a missing closing brace when
output was cut off) or call a tool by a near-miss name (`ReadFile`, `bash`,
`functions.read_file`). Repairing these instead of rejecting them saves a
turn and keeps the model from getting stuck.
"""

from __future__ import annotations

import ast
import json
import re
from typing import Any, Dict, Iterable, Optional

# Common names models use for Joshu's built-in tools
TOOL_ALIASES = {
    "read": "read_file",
    "readfile": "read_file",
    "view": "read_file",
    "cat": "read_file",
    "open_file": "read_file",
    "write": "write_file",
    "writefile": "write_file",
    "create_file": "write_file",
    "edit": "replace",
    "edit_file": "replace",
    "str_replace": "replace",
    "replace_in_file": "replace",
    "bash": "run_shell_command",
    "shell": "run_shell_command",
    "run": "run_shell_command",
    "exec": "run_shell_command",
    "execute": "run_shell_command",
    "execute_command": "run_shell_command",
    "run_command": "run_shell_command",
    "terminal": "run_shell_command",
    "grep": "search_file_content",
    "search": "search_file_content",
    "ripgrep": "search_file_content",
    "ls": "list_directory",
    "list_dir": "list_directory",
    "list_files": "list_directory",
    "find_files": "glob",
    "todo": "write_todos",
    "todos": "write_todos",
}

_PREFIXES = ("functions.", "function.", "tools.", "tool.", "default_api.")
_FENCE = re.compile(r"^```[a-zA-Z0-9_-]*\s*\n?(.*?)\n?```$", re.DOTALL)
_TRAILING_COMMA = re.compile(r",(\s*[}\]])")


def repair_arguments(raw: Optional[str]) -> Dict[str, Any]:
    """
    Decode tool arguments, repairing common mistakes.

    Raises:
        ValueError: the arguments can't be understood as an object.
    """
    text = (raw or "").strip()
    if not text:
        return {}

    candidates = [text]
    fenced = _FENCE.match(text)
    if fenced:
        candidates.append(fenced.group(1).strip())
    for candidate in list(candidates):
        # Text around the object ("Here are the arguments: {...}")
        start, end = candidate.find("{"), candidate.rfind("}")
        if start > 0 or (end != -1 and end < len(candidate) - 1):
            if start != -1 and end > start:
                candidates.append(candidate[start : end + 1])

    first_error: Optional[Exception] = None
    for candidate in candidates:
        for attempt in (candidate, _TRAILING_COMMA.sub(r"\1", candidate), _close(candidate)):
            try:
                value = _decode(attempt)
            except (ValueError, SyntaxError) as e:
                first_error = first_error or e
                continue
            if isinstance(value, dict):
                return value
    raise ValueError(f"tool arguments must be a JSON object ({first_error or 'not an object'})")


def _decode(text: str) -> Any:
    try:
        value = json.loads(text)
    except ValueError:
        # Python literals: single quotes, True/False/None
        value = ast.literal_eval(text)
    # Double-encoded: "{\"path\": \"a\"}"
    if isinstance(value, str) and value.strip().startswith("{"):
        value = json.loads(value)
    return value


def _close(text: str) -> str:
    """Close strings, arrays and objects left open by truncated output."""
    stack = []
    in_string = False
    escaped = False
    for char in text:
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
        elif char == '"':
            in_string = True
        elif char in "{[":
            stack.append("}" if char == "{" else "]")
        elif char in "}]" and stack:
            stack.pop()
    closed = text + ('"' if in_string else "")
    closed = _TRAILING_COMMA.sub(r"\1", closed.rstrip().rstrip(",") + "".join(reversed(stack)))
    return closed


def resolve_tool_name(name: str, available: Iterable[str]) -> Optional[str]:
    """The available tool a near-miss name refers to, or None."""
    names = list(available)
    if name in names:
        return name

    candidate = name.strip()
    for prefix in _PREFIXES:
        if candidate.lower().startswith(prefix):
            candidate = candidate[len(prefix) :]
    if candidate in names:
        return candidate

    by_key = {_key(n): n for n in names}
    key = _key(candidate)
    if key in by_key:
        return by_key[key]
    alias = TOOL_ALIASES.get(_snake(candidate)) or TOOL_ALIASES.get(key)
    if alias in names:
        return alias
    return None


def _key(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", name.lower())


def _snake(name: str) -> str:
    name = re.sub(r"(?<=[a-z0-9])([A-Z])", r"_\1", name)
    return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")
