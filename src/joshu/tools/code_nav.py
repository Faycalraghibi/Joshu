"""
code_nav: go to definition, find references and hover, through the language
server for the file's language (see joshu.core.lsp).
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from joshu.core.tool_registry import register_tool
from joshu.tools.filesystem_tools import get_workspace_root, resolve_path

MAX_LOCATIONS = 50
# Lines that likely define a symbol, for finding it when no line is given
_DEFINITION = (
    r"(?:def|class|function|func|fn|const|let|var|type|interface|struct|enum|trait|impl)\s+"
)


def locate_symbol(text: str, symbol: str, line: Optional[int]) -> Optional[Tuple[int, int]]:
    """(line, column), 1-based, of `symbol` on `line`, or of its likely definition."""
    lines = text.splitlines()
    word = re.compile(rf"(?<![\w$]){re.escape(symbol)}(?![\w$])")
    if line is not None:
        if not 1 <= line <= len(lines):
            return None
        match = word.search(lines[line - 1])
        return (line, match.start() + 1) if match else None
    definition = re.compile(_DEFINITION + re.escape(symbol) + r"(?![\w$])")
    for number, content in enumerate(lines, 1):
        match = definition.search(content)
        if match:
            return number, match.end() - len(symbol) + 1
    for number, content in enumerate(lines, 1):
        match = word.search(content)
        if match:
            return number, match.start() + 1
    return None


def _label(path: Path) -> str:
    try:
        return str(path.relative_to(get_workspace_root().resolve()))
    except ValueError:
        return str(path)


def _source_line(path: Path, line: int) -> str:
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        return lines[line - 1].strip()[:160] if 0 < line <= len(lines) else ""
    except OSError:
        return ""


@register_tool(
    name="code_nav",
    description="Ask the language server: definition (where a symbol is defined), "
    "references (where it is used) or hover (its type and docs). Give the file and the "
    "symbol; add line (1-based) to pick an occurrence, or column for an exact position.",
    parameters={
        "type": "object",
        "properties": {
            "action": {"type": "string", "enum": ["definition", "references", "hover"]},
            "path": {"type": "string"},
            "symbol": {"type": "string"},
            "line": {"type": "integer"},
            "column": {"type": "integer"},
        },
        "required": ["action", "path"],
    },
    enabled=True,
    requires_approval=False,
)
def code_nav_tool(
    action: str,
    path: str,
    symbol: str = "",
    line: Optional[int] = None,
    column: Optional[int] = None,
) -> Dict[str, Any]:
    from joshu.core.lsp import LSPError, get_lsp_manager

    try:
        resolved = resolve_path(path)
    except ValueError as e:
        return {"success": False, "error": str(e)}
    if not resolved.is_file():
        return {"success": False, "error": f"File not found: {path}"}

    if line is None or column is None:
        if not symbol:
            return {
                "success": False,
                "error": "Give symbol (and optionally line), or line and column",
            }
        text = resolved.read_text(encoding="utf-8", errors="replace")
        position = locate_symbol(text, symbol, line)
        if position is None:
            where = f" on line {line}" if line else ""
            return {"success": False, "error": f"'{symbol}' not found{where} in {path}"}
        line, column = position

    manager = get_lsp_manager(get_workspace_root())
    found = manager.client_for(resolved)
    if found is None:
        return {
            "success": False,
            "error": f"No language server for {resolved.suffix} files. Install one (e.g. "
            "pip install basedpyright for Python), or use search_file_content.",
        }
    client, language_id = found
    try:
        if action == "hover":
            info = client.hover(resolved, language_id, line, column)
            return {"success": True, "hover": info or "(no information)"}
        method = {
            "definition": "textDocument/definition",
            "references": "textDocument/references",
        }.get(action)
        if method is None:
            return {"success": False, "error": "action must be definition, references or hover"}
        locations = client.locations(method, resolved, language_id, line, column)
    except (LSPError, OSError) as e:
        return {"success": False, "error": f"Language server error: {e}"}

    results = [
        f"{_label(loc.path)}:{loc.line}:{loc.column}: {_source_line(loc.path, loc.line)}"
        for loc in locations[:MAX_LOCATIONS]
    ]
    response: Dict[str, Any] = {"success": True, "action": action, "results": results}
    if len(locations) > MAX_LOCATIONS:
        response["more"] = len(locations) - MAX_LOCATIONS
    if not results:
        response["message"] = "No results"
    return response
