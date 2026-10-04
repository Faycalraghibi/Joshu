"""
Editing tools beyond `replace`: several edits to one file at once, and
Jupyter notebook cells.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

from joshu.core.tool_registry import register_tool
from joshu.tools.filesystem_tools import (
    _closest_match,
    _with_line_endings,
    generate_diff,
    resolve_path,
)

logger = logging.getLogger(__name__)


# =============================================================================
# MULTI EDIT
# =============================================================================


def apply_edits(content: str, edits: List[Dict[str, Any]]) -> str:
    """
    Apply edits in order to `content` (each sees the result of the previous).

    Raises:
        ValueError: an edit's old_string is missing or ambiguous; nothing is applied.
    """
    crlf = "\r\n" in content
    for number, edit in enumerate(edits, start=1):
        old = str(edit.get("old_string", ""))
        new = str(edit.get("new_string", ""))
        every = bool(edit.get("all_occurrences", False))
        if crlf:
            old, new = _with_line_endings(old, "\r\n"), _with_line_endings(new, "\r\n")
        if not old:
            raise ValueError(f"edit {number}: old_string is empty")
        if old == new:
            raise ValueError(f"edit {number}: old_string and new_string are the same")
        count = content.count(old)
        if count == 0:
            hint = _closest_match(content, old).get("hint", "")
            raise ValueError(
                f"edit {number}: old_string not found (after the earlier edits). {hint}".strip()
            )
        if count > 1 and not every:
            raise ValueError(
                f"edit {number}: old_string appears {count} times; add context or set "
                "all_occurrences"
            )
        content = content.replace(old, new) if every else content.replace(old, new, 1)
    return content


@register_tool(
    name="multi_edit",
    description="Make several exact-text edits to one file in one call. Edits apply in "
    "order; if any fails, none is applied. The user may be asked to approve.",
    parameters={
        "type": "object",
        "properties": {
            "path": {"type": "string"},
            "edits": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "old_string": {"type": "string", "description": "Exact current text"},
                        "new_string": {"type": "string"},
                        "all_occurrences": {"type": "boolean"},
                    },
                    "required": ["old_string", "new_string"],
                },
            },
        },
        "required": ["path", "edits"],
    },
    enabled=True,
    requires_approval=True,
)
def multi_edit_tool(path: str, edits: List[Dict[str, Any]]) -> Dict[str, Any]:
    try:
        if not isinstance(edits, list) or not edits:
            return {"success": False, "error": "edits must be a non-empty list"}
        resolved = resolve_path(path)
        if not resolved.is_file():
            return {"success": False, "error": f"File not found: {path}"}
        original = resolved.read_bytes().decode("utf-8")
        try:
            updated = apply_edits(original, edits)
        except ValueError as e:
            return {"success": False, "error": f"{e}. No edits were applied."}
        diff = generate_diff(
            original.replace("\r\n", "\n"), updated.replace("\r\n", "\n"), resolved.name
        )
        resolved.write_bytes(updated.encode("utf-8"))
        return {
            "success": True,
            "path": path,
            "edits": len(edits),
            "diff": diff,
            "message": f"Applied {len(edits)} edit(s)",
        }
    except ValueError as e:
        return {"success": False, "error": str(e)}
    except Exception as e:
        logger.error(f"multi_edit failed: {e}")
        return {"success": False, "error": f"Failed to edit file: {e}"}


# =============================================================================
# NOTEBOOK EDIT
# =============================================================================


def _source_lines(text: str) -> List[str]:
    """Notebook cell source as nbformat stores it: lines keeping their newlines."""
    lines = text.splitlines(keepends=True)
    return lines


def _find_cell(cells: List[Dict[str, Any]], cell_id: Optional[str], index: Optional[int]) -> int:
    if cell_id:
        for position, cell in enumerate(cells):
            if cell.get("id") == cell_id:
                return position
        raise ValueError(f"No cell with id {cell_id!r}")
    if index is None:
        raise ValueError("Give cell_id or cell_index")
    if not 0 <= index < len(cells):
        raise ValueError(f"cell_index {index} is out of range (0-{len(cells) - 1})")
    return index


def edit_notebook(
    notebook: Dict[str, Any],
    new_source: str = "",
    cell_id: Optional[str] = None,
    cell_index: Optional[int] = None,
    cell_type: Optional[str] = None,
    edit_mode: str = "replace",
) -> str:
    """Change `notebook` in place; returns a short description of the change."""
    cells = notebook.setdefault("cells", [])
    if edit_mode == "insert":
        if cell_id or cell_index is not None:
            position = _find_cell(cells, cell_id, cell_index) + 1
        else:
            position = 0
        kind = cell_type or "code"
        cell: Dict[str, Any] = {
            "cell_type": kind,
            "metadata": {},
            "source": _source_lines(new_source),
        }
        if notebook.get("nbformat", 4) >= 4 and notebook.get("nbformat_minor", 5) >= 5:
            import uuid

            cell["id"] = uuid.uuid4().hex[:8]
        if kind == "code":
            cell.update({"execution_count": None, "outputs": []})
        cells.insert(position, cell)
        return f"Inserted a {kind} cell at index {position}"

    position = _find_cell(cells, cell_id, cell_index)
    if edit_mode == "delete":
        cells.pop(position)
        return f"Deleted cell {position}"
    if edit_mode != "replace":
        raise ValueError("edit_mode must be replace, insert or delete")

    cell = cells[position]
    cell["source"] = _source_lines(new_source)
    if cell_type and cell_type != cell.get("cell_type"):
        cell["cell_type"] = cell_type
        if cell_type == "code":
            cell.setdefault("execution_count", None)
            cell.setdefault("outputs", [])
        else:
            cell.pop("outputs", None)
            cell.pop("execution_count", None)
    if cell.get("cell_type") == "code":
        # The old outputs no longer match the code
        cell["outputs"] = []
        cell["execution_count"] = None
    return f"Replaced cell {position}"


@register_tool(
    name="notebook_edit",
    description="Edit a Jupyter notebook (.ipynb) cell: replace its source, insert a new "
    "cell after it (or at the start), or delete it. Identify the cell by cell_id or "
    "0-based cell_index. The user may be asked to approve.",
    parameters={
        "type": "object",
        "properties": {
            "path": {"type": "string"},
            "new_source": {"type": "string"},
            "cell_id": {"type": "string"},
            "cell_index": {"type": "integer"},
            "cell_type": {"type": "string", "enum": ["code", "markdown"]},
            "edit_mode": {"type": "string", "enum": ["replace", "insert", "delete"]},
        },
        "required": ["path"],
    },
    enabled=True,
    requires_approval=True,
)
def notebook_edit_tool(
    path: str,
    new_source: str = "",
    cell_id: Optional[str] = None,
    cell_index: Optional[int] = None,
    cell_type: Optional[str] = None,
    edit_mode: str = "replace",
) -> Dict[str, Any]:
    try:
        resolved = resolve_path(path)
        if resolved.suffix.lower() != ".ipynb":
            return {"success": False, "error": "notebook_edit only edits .ipynb files"}
        if not resolved.is_file():
            return {"success": False, "error": f"File not found: {path}"}
        notebook = json.loads(resolved.read_text(encoding="utf-8"))
        message = edit_notebook(notebook, new_source, cell_id, cell_index, cell_type, edit_mode)
        resolved.write_text(
            json.dumps(notebook, indent=1, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        return {
            "success": True,
            "path": path,
            "message": message,
            "cells": len(notebook.get("cells", [])),
        }
    except (ValueError, json.JSONDecodeError) as e:
        return {"success": False, "error": str(e)}
    except Exception as e:
        logger.error(f"notebook_edit failed: {e}")
        return {"success": False, "error": f"Failed to edit notebook: {e}"}
