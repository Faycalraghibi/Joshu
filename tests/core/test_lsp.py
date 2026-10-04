"""Language server client, diagnostics after edits and code_nav, against a fake server."""

import sys
import textwrap

import pytest
from test_agent_loop import FakeClient, call, make_agent, text, tool_messages

import joshu.core.lsp as lsp
from joshu.core.config import get_config_manager
from joshu.core.lsp import LSPManager, find_command, language_for, uri_to_path
from joshu.core.permissions import PermissionMode
from joshu.tools import filesystem_tools
from joshu.tools.code_nav import code_nav_tool, locate_symbol

FAKE_SERVER = textwrap.dedent(
    r"""
    import json, sys

    def read():
        length = None
        while True:
            line = sys.stdin.buffer.readline()
            if not line:
                sys.exit(0)
            line = line.strip()
            if not line:
                break
            if line.lower().startswith(b"content-length:"):
                length = int(line.split(b":")[1])
        return json.loads(sys.stdin.buffer.read(length))

    def send(message):
        body = json.dumps(message).encode()
        sys.stdout.buffer.write(b"Content-Length: %d\r\n\r\n" % len(body) + body)
        sys.stdout.buffer.flush()

    def publish(uri, text):
        diagnostics = [
            {"range": {"start": {"line": i, "character": line.index("BAD")}, "end": {"line": i, "character": 0}},
             "severity": 1, "message": "BAD is not defined", "source": "fake"}
            for i, line in enumerate(text.splitlines()) if "BAD" in line
        ]
        diagnostics.append({"range": {"start": {"line": 0, "character": 0}, "end": {"line": 0, "character": 0}},
                            "severity": 2, "message": "just a warning"})
        send({"jsonrpc": "2.0", "method": "textDocument/publishDiagnostics",
              "params": {"uri": uri, "diagnostics": diagnostics}})

    while True:
        message = read()
        method = message.get("method")
        params = message.get("params") or {}
        if method == "initialize":
            send({"jsonrpc": "2.0", "id": message["id"], "result": {"capabilities": {}}})
        elif method == "textDocument/didOpen":
            publish(params["textDocument"]["uri"], params["textDocument"]["text"])
        elif method == "textDocument/didChange":
            publish(params["textDocument"]["uri"], params["contentChanges"][0]["text"])
        elif method == "textDocument/definition":
            uri = params["textDocument"]["uri"]
            send({"jsonrpc": "2.0", "id": message["id"], "result": {"uri": uri,
                  "range": {"start": {"line": 0, "character": 4}, "end": {"line": 0, "character": 8}}}})
        elif method == "textDocument/references":
            uri = params["textDocument"]["uri"]
            send({"jsonrpc": "2.0", "id": message["id"], "result": [
                {"uri": uri, "range": {"start": {"line": 0, "character": 4}, "end": {}}},
                {"uri": uri, "range": {"start": {"line": 3, "character": 7}, "end": {}}}]})
        elif method == "textDocument/hover":
            send({"jsonrpc": "2.0", "id": message["id"],
                  "result": {"contents": {"kind": "markdown", "value": "def area(w, h) -> int"}}})
        elif method == "shutdown":
            send({"jsonrpc": "2.0", "id": message["id"], "result": None})
        elif method == "exit":
            sys.exit(0)
        elif "id" in message:
            send({"jsonrpc": "2.0", "id": message["id"], "result": None})
    """
)


@pytest.fixture
def workspace(tmp_path):
    server = tmp_path / "fake_server.py"
    server.write_text(FAKE_SERVER, encoding="utf-8")
    project = tmp_path / "project"
    project.mkdir()
    (project / "shapes.py").write_text(
        "def area(w, h):\n    return w * h\n\nprint(area(2, 3))\n", encoding="utf-8"
    )
    filesystem_tools.set_workspace_root(project)
    lsp.reset_lsp_manager()
    lsp._manager = LSPManager(root=project, settings={"python": [sys.executable, str(server)]})
    yield project
    lsp.reset_lsp_manager()
    filesystem_tools._workspace_root = None


def test_diagnostics_follow_the_file(workspace):
    manager = lsp.get_lsp_manager()
    path = workspace / "shapes.py"
    assert manager.diagnostics(path) == []  # only a warning, errors_only

    path.write_text("x = BAD\n", encoding="utf-8")
    errors = manager.diagnostics(path)
    assert [(e.line, e.column, e.message) for e in errors] == [(1, 5, "BAD is not defined")]
    assert errors[0].format("shapes.py") == "shapes.py:1:5: error: BAD is not defined [fake]"

    path.write_text("x = 1\n", encoding="utf-8")
    assert manager.diagnostics(path) == []
    assert manager.status()["python"].startswith("running")


def test_agent_gets_language_server_errors_after_an_edit(workspace):
    client = FakeClient(
        [
            call("replace", path="shapes.py", old_string="w * h", new_string="w * h  # BAD"),
            text("ok"),
        ]
    )
    agent = make_agent(client, mode=PermissionMode.ACCEPT_EDITS, cwd=workspace)
    agent.run("edit")
    output = tool_messages(agent.messages)[0]["content"]
    assert "now has problems" in output
    assert "shapes.py:2:21: error: BAD is not defined" in output


def test_code_nav(workspace):
    definition = code_nav_tool("definition", "shapes.py", symbol="area", line=4)
    assert definition["results"] == ["shapes.py:1:5: def area(w, h):"]
    references = code_nav_tool("references", "shapes.py", symbol="area")
    assert len(references["results"]) == 2
    assert code_nav_tool("hover", "shapes.py", line=1, column=5)["hover"] == "def area(w, h) -> int"
    missing = code_nav_tool("definition", "shapes.py", symbol="nothing")
    assert not missing["success"] and "not found" in missing["error"]


def test_no_server_for_the_language(workspace):
    (workspace / "notes.md").write_text("# hi", encoding="utf-8")
    result = code_nav_tool("definition", "notes.md", line=1, column=1)
    assert not result["success"] and "No language server" in result["error"]
    assert lsp.get_lsp_manager().diagnostics(workspace / "notes.md") is None


def test_lsp_can_be_turned_off(workspace):
    lsp._manager = LSPManager(root=workspace, settings=False)
    assert lsp.get_lsp_manager().diagnostics(workspace / "shapes.py") is None
    assert get_config_manager().set("lsp", False)
    assert get_config_manager().set("lsp", {"python": "pylsp"})
    get_config_manager().set("lsp", {})


def test_locate_symbol():
    source = "import os\n\ndef area(w, h):\n    return w * h\n\nx = area(1, 2)\n"
    assert locate_symbol(source, "area", None) == (3, 5)  # the definition
    assert locate_symbol(source, "area", 6) == (6, 5)
    assert locate_symbol(source, "are", None) is None  # whole words only
    assert locate_symbol(source, "area", 99) is None


def test_helpers(tmp_path):
    assert language_for(tmp_path / "a.tsx") == "typescript"
    assert language_for(tmp_path / "a.txt") is None
    assert uri_to_path((tmp_path / "a b.py").resolve().as_uri()) == (tmp_path / "a b.py").resolve()
    assert find_command("go", {"go": ""}) is None
    assert find_command("python", {"python": [sys.executable]}) == [sys.executable]
