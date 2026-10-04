"""
Lean tool definitions for model requests.

Tool definitions are sent with every request, so they are trimmed before
sending: rarely used optional parameters are left out (the tools still accept
them) and parameter descriptions are kept to what the model needs.
"""

from __future__ import annotations

import copy
import re
from typing import Any, Dict

# Optional parameters the model rarely needs; their defaults are what it wants
HIDDEN_PARAMETERS = {
    "list_directory": {"ignore_patterns", "respect_gitignore", "show_hidden"},
    "glob": {"case_sensitive", "respect_gitignore", "max_results"},
    "search_file_content": {"case_sensitive", "max_results"},
    "read_file": {"encoding"},
    "write_file": {"encoding"},
    "write_todos": {"task_name"},
}

# Short parameter descriptions (tool -> parameter -> description; "" drops it)
SHORT_DESCRIPTIONS: Dict[str, Dict[str, str]] = {
    "list_directory": {"path": ""},
    "glob": {"pattern": "e.g. **/*.py", "path": ""},
    "search_file_content": {"pattern": "Regex", "path": "", "file_pattern": "e.g. *.py"},
    "read_file": {"path": "", "start_line": "1-based", "end_line": "Inclusive"},
    "write_file": {"path": "", "content": ""},
    "replace": {
        "path": "",
        "old_string": "Exact current text",
        "new_string": "",
        "all_occurrences": "",
    },
    "run_shell_command": {
        "command": "",
        "timeout": "Seconds (default 60)",
        "working_directory": "",
        "background": "For servers and other long-running commands",
    },
}

MAX_DESCRIPTION = 80
_PARENTHETICAL = re.compile(r"\s*\((?:default|e\.g\.|relative|optional)[^)]*\)", re.IGNORECASE)


def lean_definition(definition: Dict[str, Any]) -> Dict[str, Any]:
    """A trimmed copy of an OpenAI-format tool definition."""
    lean = copy.deepcopy(definition)
    function = lean.get("function") or {}
    name = function.get("name", "")
    parameters = function.get("parameters") or {}
    properties = parameters.get("properties")
    if not isinstance(properties, dict):
        return lean

    hidden = HIDDEN_PARAMETERS.get(name, set())
    required = set(parameters.get("required") or [])
    short = SHORT_DESCRIPTIONS.get(name, {})
    for key in list(properties):
        if key in hidden and key not in required:
            del properties[key]
            continue
        prop = properties[key]
        if not isinstance(prop, dict):
            continue
        if key in short:
            if short[key]:
                prop["description"] = short[key]
            else:
                prop.pop("description", None)
        elif isinstance(prop.get("description"), str):
            prop["description"] = _shorten(prop["description"])
        _lean_nested(prop)
    return lean


def _lean_nested(prop: Dict[str, Any]) -> None:
    """Shorten descriptions inside array items / nested objects."""
    items = prop.get("items")
    if isinstance(items, dict):
        for value in (items.get("properties") or {}).values():
            if isinstance(value, dict) and isinstance(value.get("description"), str):
                value["description"] = _shorten(value["description"])
        if isinstance(items.get("description"), str):
            items["description"] = _shorten(items["description"])


def _shorten(text: str) -> str:
    text = _PARENTHETICAL.sub("", " ".join(text.split())).strip()
    if len(text) > MAX_DESCRIPTION:
        cut = text[:MAX_DESCRIPTION]
        text = cut[: cut.rfind(" ")].rstrip(",;:") + "…" if " " in cut else cut
    return text
