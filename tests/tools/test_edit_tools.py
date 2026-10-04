"""multi_edit, notebook_edit, quoted @image paths and clipboard images."""

import json
import sys
import types
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from joshu.core.images import find_image_refs
from joshu.core.permissions import PermissionManager, PermissionMode, build_preview
from joshu.tools import filesystem_tools
from joshu.tools.edit_tools import multi_edit_tool, notebook_edit_tool


@pytest.fixture
def workspace(tmp_path):
    filesystem_tools.set_workspace_root(tmp_path)
    yield tmp_path
    filesystem_tools._workspace_root = None


# ------------------------------------------------------------------ multi_edit


def test_edits_apply_in_order(workspace):
    (workspace / "a.py").write_text("x = 1\ny = 2\nz = x\n", encoding="utf-8")
    result = multi_edit_tool(
        "a.py",
        [
            {"old_string": "x = 1", "new_string": "count = 1"},
            {"old_string": "z = x", "new_string": "z = count"},
        ],
    )
    assert result["success"] and result["edits"] == 2
    assert (workspace / "a.py").read_text(encoding="utf-8") == "count = 1\ny = 2\nz = count\n"
    assert "-x = 1" in result["diff"] and "+count = 1" in result["diff"]


def test_a_failing_edit_applies_nothing(workspace):
    (workspace / "a.py").write_text("a = 1\nb = 2\n", encoding="utf-8")
    result = multi_edit_tool(
        "a.py",
        [
            {"old_string": "a = 1", "new_string": "a = 10"},
            {"old_string": "missing", "new_string": "x"},
        ],
    )
    assert not result["success"] and "edit 2" in result["error"]
    assert "No edits were applied" in result["error"]
    assert (workspace / "a.py").read_text(encoding="utf-8") == "a = 1\nb = 2\n"


def test_ambiguous_and_all_occurrences(workspace):
    (workspace / "a.py").write_text("v = 0\nv = 0\n", encoding="utf-8")
    result = multi_edit_tool("a.py", [{"old_string": "v = 0", "new_string": "v = 1"}])
    assert not result["success"] and "appears 2 times" in result["error"]
    result = multi_edit_tool(
        "a.py", [{"old_string": "v = 0", "new_string": "v = 1", "all_occurrences": True}]
    )
    assert result["success"]
    assert (workspace / "a.py").read_text(encoding="utf-8") == "v = 1\nv = 1\n"


def test_crlf_files_keep_their_line_endings(workspace):
    (workspace / "w.py").write_bytes(b"a = 1\r\nb = 2\r\n")
    assert multi_edit_tool("w.py", [{"old_string": "a = 1\nb = 2", "new_string": "a = 3\nb = 4"}])[
        "success"
    ]
    assert (workspace / "w.py").read_bytes() == b"a = 3\r\nb = 4\r\n"


def test_multi_edit_is_an_edit_tool(workspace):
    (workspace / "a.py").write_text("x = 1\n", encoding="utf-8")
    manager = PermissionManager(PermissionMode.ACCEPT_EDITS)
    edits = [{"old_string": "x = 1", "new_string": "x = 2"}]
    assert manager.check("multi_edit", {"path": "a.py", "edits": edits}, True).allowed
    preview = build_preview("multi_edit", {"path": "a.py", "edits": edits})
    assert "-x = 1" in preview and "+x = 2" in preview
    asked = PermissionManager(PermissionMode.ACCEPT_EDITS).check(
        "multi_edit", {"path": ".env", "edits": edits}, True
    )
    assert not asked.allowed  # protected file, no approver


# --------------------------------------------------------------- notebook_edit


def notebook(workspace):
    data = {
        "nbformat": 4,
        "nbformat_minor": 5,
        "metadata": {},
        "cells": [
            {"id": "intro", "cell_type": "markdown", "metadata": {}, "source": ["# Title\n"]},
            {
                "id": "load",
                "cell_type": "code",
                "metadata": {},
                "execution_count": 3,
                "outputs": [{"output_type": "stream", "text": ["old\n"]}],
                "source": ["x = 1\n"],
            },
        ],
    }
    path = workspace / "nb.ipynb"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def cells(path):
    return json.loads(path.read_text(encoding="utf-8"))["cells"]


def test_replace_cell_clears_stale_outputs(workspace):
    path = notebook(workspace)
    result = notebook_edit_tool("nb.ipynb", "x = 2\nprint(x)", cell_id="load")
    assert result["success"]
    cell = cells(path)[1]
    assert cell["source"] == ["x = 2\n", "print(x)"]
    assert cell["outputs"] == [] and cell["execution_count"] is None


def test_insert_and_delete(workspace):
    path = notebook(workspace)
    notebook_edit_tool(
        "nb.ipynb", "## Setup", cell_index=0, cell_type="markdown", edit_mode="insert"
    )
    assert [c["cell_type"] for c in cells(path)] == ["markdown", "markdown", "code"]
    assert cells(path)[1]["source"] == ["## Setup"] and cells(path)[1].get("id")
    notebook_edit_tool("nb.ipynb", "import os", edit_mode="insert")
    assert cells(path)[0]["source"] == ["import os"] and cells(path)[0]["outputs"] == []
    notebook_edit_tool("nb.ipynb", cell_id="intro", edit_mode="delete")
    assert all(c.get("id") != "intro" for c in cells(path))


def test_notebook_errors(workspace):
    notebook(workspace)
    (workspace / "a.py").write_text("x", encoding="utf-8")
    assert "only edits .ipynb" in notebook_edit_tool("a.py", "x")["error"]
    assert "out of range" in notebook_edit_tool("nb.ipynb", "x", cell_index=9)["error"]
    assert "No cell with id" in notebook_edit_tool("nb.ipynb", "x", cell_id="nope")["error"]


def test_new_tools_load_on_demand(workspace):
    from joshu.core.agent import Agent

    agent = Agent(client=MagicMock(model="m", context_window=None), permissions=PermissionManager())
    offered = [t["function"]["name"] for t in agent.request_tools()]
    assert "multi_edit" not in offered and "notebook_edit" not in offered
    assert {s.name for s in agent.deferred_tools()} >= {"multi_edit", "notebook_edit"}


# ------------------------------------------------------------------ images


def test_quoted_image_paths_with_spaces(tmp_path):
    folder = tmp_path / "my shots"
    folder.mkdir()
    image = folder / "screen 1.png"
    image.write_bytes(b"\x89PNG\r\n\x1a\n")
    text, paths = find_image_refs(f'look at @"{image}" please')
    assert paths == [image] and text == "look at [image: screen 1.png] please"


def fake_pillow(monkeypatch, content):
    class Image:
        def save(self, path, fmt):
            Path(path).write_bytes(b"\x89PNG\r\n\x1a\n")

    image_module = types.SimpleNamespace(Image=Image)
    grab = types.SimpleNamespace(grabclipboard=lambda: content(Image))
    pil = types.ModuleType("PIL")
    pil.Image = image_module
    pil.ImageGrab = grab
    monkeypatch.setitem(sys.modules, "PIL", pil)
    monkeypatch.setitem(sys.modules, "PIL.Image", image_module)
    monkeypatch.setitem(sys.modules, "PIL.ImageGrab", grab)


def test_clipboard_image_is_saved(tmp_path, monkeypatch):
    from joshu.ui.clipboard import grab_clipboard_image, image_reference

    fake_pillow(monkeypatch, lambda Image: Image())
    path = grab_clipboard_image(tmp_path)
    assert path.is_file() and path.suffix == ".png"
    spaced = Path("a b") / "x.png"
    assert image_reference(spaced) == f'@"{spaced}" '
    assert image_reference(Path("x.png")) == "@x.png "


def test_clipboard_without_image(tmp_path, monkeypatch):
    from joshu.ui.clipboard import grab_clipboard_image

    fake_pillow(monkeypatch, lambda Image: None)
    assert grab_clipboard_image(tmp_path) is None


def test_clipboard_without_pillow(monkeypatch):
    from joshu.ui.clipboard import ClipboardError, grab_clipboard_image

    monkeypatch.setitem(sys.modules, "PIL", None)
    with pytest.raises(ClipboardError, match="pip install pillow"):
        grab_clipboard_image()


def test_paste_command_attaches_to_next_prompt(tmp_path, monkeypatch):
    from joshu.ui.interactive.commands import CommandHandler

    monkeypatch.setenv("JOSHU_HOME", str(tmp_path))
    fake_pillow(monkeypatch, lambda Image: Image())
    mode = MagicMock(type_ahead="")
    CommandHandler(mode).handle_slash_command("/paste")
    assert mode.type_ahead.startswith("@") and ".png" in mode.type_ahead
