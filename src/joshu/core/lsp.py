"""
Language servers: real type and compile errors after edits, and code navigation.

Joshu starts an installed language server for a file's language the first time
it is needed and keeps it running for the session:

    Python                  basedpyright-langserver, pyright-langserver, pylsp
    JavaScript / TypeScript typescript-language-server
    Go                      gopls
    Rust                    rust-analyzer

After the agent edits a file, the server's errors for that file go back to the
model (alongside the built-in syntax checks). The `code_nav` tool asks the
server for definitions, references and hover information.

Configure with the `lsp` setting: `false` turns language servers off, and
`{python: "pylsp", rust: ""}` picks a command per language ("" disables one).
"""

from __future__ import annotations

import atexit
import json
import logging
import os
import shlex
import shutil
import subprocess
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import unquote, urlparse
from urllib.request import url2pathname

logger = logging.getLogger(__name__)

# language -> (file extensions, LSP languageId per extension, candidate commands)
LANGUAGES: Dict[str, Tuple[Dict[str, str], List[List[str]]]] = {
    "python": (
        {".py": "python", ".pyi": "python"},
        [
            ["basedpyright-langserver", "--stdio"],
            ["pyright-langserver", "--stdio"],
            ["pylsp"],
        ],
    ),
    "typescript": (
        {
            ".ts": "typescript",
            ".tsx": "typescriptreact",
            ".js": "javascript",
            ".jsx": "javascriptreact",
            ".mjs": "javascript",
            ".cjs": "javascript",
        },
        [["typescript-language-server", "--stdio"]],
    ),
    "go": ({".go": "go"}, [["gopls"]]),
    "rust": ({".rs": "rust"}, [["rust-analyzer"]]),
}

STARTUP_TIMEOUT = 20.0
REQUEST_TIMEOUT = 15.0
DIAGNOSTICS_TIMEOUT = 8.0  # wait for errors after an edit
DIAGNOSTICS_SETTLE = 0.6  # servers may publish more than once; wait for quiet
SEVERITY = {1: "error", 2: "warning", 3: "info", 4: "hint"}


class LSPError(Exception):
    """The language server failed or isn't available."""


@dataclass
class Diagnostic:
    line: int  # 1-based
    column: int  # 1-based
    severity: str
    message: str
    source: str = ""

    def format(self, path_label: str) -> str:
        source = f" [{self.source}]" if self.source else ""
        return f"{path_label}:{self.line}:{self.column}: {self.severity}: {self.message}{source}"


@dataclass
class Location:
    path: Path
    line: int  # 1-based
    column: int  # 1-based


# ------------------------------------------------------------------ helpers


def path_to_uri(path: Path) -> str:
    return path.resolve().as_uri()


def uri_to_path(uri: str) -> Path:
    parsed = urlparse(uri)
    return Path(url2pathname(unquote(parsed.path))).resolve()


def language_for(path: Path) -> Optional[str]:
    suffix = path.suffix.lower()
    for language, (extensions, _commands) in LANGUAGES.items():
        if suffix in extensions:
            return language
    return None


def find_command(language: str, configured: Any = None) -> Optional[List[str]]:
    """The command to run for `language`: configured, or the first one installed."""
    if isinstance(configured, dict) and language in configured:
        value = configured[language]
        if not value:
            return None
        if isinstance(value, str):
            argv = [part.strip('"') for part in shlex.split(value, posix=os.name != "nt")]
        else:
            argv = [str(part) for part in value]
        return argv if argv and shutil.which(argv[0]) else None
    for argv in LANGUAGES[language][1]:
        if shutil.which(argv[0]):
            return list(argv)
    return None


# ------------------------------------------------------------------- client


@dataclass
class _Document:
    version: int
    text: str


class LSPClient:
    """One running language server, spoken to over stdio with JSON-RPC."""

    def __init__(self, argv: List[str], root: Path, language: str) -> None:
        self.argv = argv
        self.root = root.resolve()
        self.language = language
        self._process: Optional[subprocess.Popen] = None
        self._next_id = 0
        self._pending: Dict[int, Dict[str, Any]] = {}
        self._lock = threading.Lock()
        self._cond = threading.Condition(self._lock)
        self._diagnostics: Dict[str, List[Dict[str, Any]]] = {}
        self._diagnostics_at: Dict[str, float] = {}
        self._documents: Dict[str, _Document] = {}
        self._alive = False

    # -------------------------------------------------------------- lifecycle

    def start(self) -> None:
        executable = shutil.which(self.argv[0]) or self.argv[0]
        try:
            self._process = subprocess.Popen(
                [executable, *self.argv[1:]],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                cwd=str(self.root),
            )
        except OSError as e:
            raise LSPError(f"Could not start {self.argv[0]}: {e}") from e
        self._alive = True
        threading.Thread(target=self._reader, name=f"lsp-{self.language}", daemon=True).start()
        self.request(
            "initialize",
            {
                "processId": os.getpid(),
                "rootUri": path_to_uri(self.root),
                "workspaceFolders": [{"uri": path_to_uri(self.root), "name": self.root.name}],
                "capabilities": {
                    "textDocument": {
                        "synchronization": {"didSave": True},
                        "publishDiagnostics": {"versionSupport": True},
                        "definition": {"linkSupport": True},
                        "references": {},
                        "hover": {"contentFormat": ["plaintext", "markdown"]},
                    },
                    "workspace": {"workspaceFolders": True, "configuration": True},
                },
            },
            timeout=STARTUP_TIMEOUT,
        )
        self.notify("initialized", {})

    def stop(self) -> None:
        if not self._alive:
            return
        try:
            self.request("shutdown", None, timeout=2)
            self.notify("exit", None)
        except LSPError:
            pass
        self._alive = False
        if self._process is not None:
            try:
                self._process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self._process.kill()

    @property
    def alive(self) -> bool:
        return self._alive and self._process is not None and self._process.poll() is None

    # --------------------------------------------------------------- protocol

    def _send(self, message: Dict[str, Any]) -> None:
        if not self.alive:
            raise LSPError(f"{self.argv[0]} is not running")
        body = json.dumps(message).encode("utf-8")
        header = f"Content-Length: {len(body)}\r\n\r\n".encode("ascii")
        try:
            assert self._process is not None and self._process.stdin is not None
            self._process.stdin.write(header + body)
            self._process.stdin.flush()
        except (OSError, ValueError) as e:
            self._alive = False
            raise LSPError(f"{self.argv[0]} stopped: {e}") from e

    def notify(self, method: str, params: Any) -> None:
        self._send({"jsonrpc": "2.0", "method": method, "params": params})

    def request(self, method: str, params: Any, timeout: float = REQUEST_TIMEOUT) -> Any:
        with self._cond:
            self._next_id += 1
            request_id = self._next_id
            self._pending[request_id] = {}
        self._send({"jsonrpc": "2.0", "id": request_id, "method": method, "params": params})
        deadline = time.monotonic() + timeout
        with self._cond:
            while "done" not in self._pending[request_id]:
                remaining = deadline - time.monotonic()
                if remaining <= 0 or not self._alive:
                    self._pending.pop(request_id, None)
                    raise LSPError(f"{method} timed out after {timeout:.0f}s ({self.argv[0]})")
                self._cond.wait(remaining)
            reply = self._pending.pop(request_id)
        if reply.get("error"):
            raise LSPError(f"{method}: {reply['error'].get('message', reply['error'])}")
        return reply.get("result")

    def _reader(self) -> None:
        stream = self._process.stdout if self._process else None
        while self._alive and stream is not None:
            try:
                length = None
                while True:
                    line = stream.readline()
                    if not line:
                        raise EOFError
                    line = line.strip()
                    if not line:
                        break
                    if line.lower().startswith(b"content-length:"):
                        length = int(line.split(b":", 1)[1])
                if length is None:
                    continue
                message = json.loads(stream.read(length).decode("utf-8"))
            except (EOFError, ValueError, OSError):
                with self._cond:
                    self._alive = False
                    self._cond.notify_all()
                return
            self._handle(message)

    def _handle(self, message: Dict[str, Any]) -> None:
        if "id" in message and "method" not in message:
            with self._cond:
                if message["id"] in self._pending:
                    self._pending[message["id"]] = {**message, "done": True}
                    self._cond.notify_all()
            return
        method = message.get("method")
        if method == "textDocument/publishDiagnostics":
            params = message.get("params") or {}
            with self._cond:
                uri = _normalize_uri(params.get("uri", ""))
                self._diagnostics[uri] = params.get("diagnostics") or []
                self._diagnostics_at[uri] = time.monotonic()
                self._cond.notify_all()
            return
        if "id" in message:
            # Requests from the server (configuration, capabilities): answer simply
            result: Any = None
            if method == "workspace/configuration":
                result = [None for _ in (message.get("params") or {}).get("items", [])]
            try:
                self._send({"jsonrpc": "2.0", "id": message["id"], "result": result})
            except LSPError:
                pass

    # -------------------------------------------------------------- documents

    def sync(self, path: Path, language_id: str) -> str:
        """Tell the server about the file's current content; returns its URI."""
        uri = _normalize_uri(path_to_uri(path))
        text = path.read_text(encoding="utf-8", errors="replace")
        document = self._documents.get(uri)
        if document is None:
            self._documents[uri] = _Document(1, text)
            self.notify(
                "textDocument/didOpen",
                {
                    "textDocument": {
                        "uri": uri,
                        "languageId": language_id,
                        "version": 1,
                        "text": text,
                    }
                },
            )
        elif document.text != text:
            document.version += 1
            document.text = text
            self.notify(
                "textDocument/didChange",
                {
                    "textDocument": {"uri": uri, "version": document.version},
                    "contentChanges": [{"text": text}],
                },
            )
            self.notify("textDocument/didSave", {"textDocument": {"uri": uri}})
        return uri

    def diagnostics(
        self, path: Path, language_id: str, timeout: float = DIAGNOSTICS_TIMEOUT
    ) -> List[Diagnostic]:
        """The server's diagnostics for `path` after syncing its current content."""
        uri = _normalize_uri(path_to_uri(path))
        with self._cond:
            self._diagnostics_at.pop(uri, None)
        self.sync(path, language_id)
        deadline = time.monotonic() + timeout
        with self._cond:
            while True:
                published = self._diagnostics_at.get(uri)
                now = time.monotonic()
                if published is not None and now - published >= DIAGNOSTICS_SETTLE:
                    break
                if now >= deadline or not self._alive:
                    break
                self._cond.wait(min(0.1, deadline - now))
            raw = list(self._diagnostics.get(uri, []))
        result = []
        for item in raw:
            start = (item.get("range") or {}).get("start") or {}
            result.append(
                Diagnostic(
                    line=int(start.get("line", 0)) + 1,
                    column=int(start.get("character", 0)) + 1,
                    severity=SEVERITY.get(item.get("severity", 1), "error"),
                    message=" ".join(str(item.get("message", "")).split()),
                    source=str(item.get("source") or ""),
                )
            )
        return result

    def locations(
        self, method: str, path: Path, language_id: str, line: int, column: int
    ) -> List[Location]:
        uri = self.sync(path, language_id)
        params: Dict[str, Any] = {
            "textDocument": {"uri": uri},
            "position": {"line": line - 1, "character": column - 1},
        }
        if method == "textDocument/references":
            params["context"] = {"includeDeclaration": True}
        result = self.request(method, params)
        if not result:
            return []
        items = result if isinstance(result, list) else [result]
        found = []
        for item in items:
            target = item.get("targetUri") or item.get("uri")
            span = item.get("targetSelectionRange") or item.get("range") or {}
            start = span.get("start") or {}
            if target:
                found.append(
                    Location(
                        uri_to_path(target),
                        int(start.get("line", 0)) + 1,
                        int(start.get("character", 0)) + 1,
                    )
                )
        return found

    def hover(self, path: Path, language_id: str, line: int, column: int) -> str:
        uri = self.sync(path, language_id)
        result = self.request(
            "textDocument/hover",
            {"textDocument": {"uri": uri}, "position": {"line": line - 1, "character": column - 1}},
        )
        if not result:
            return ""
        contents = result.get("contents")
        if isinstance(contents, dict):
            return str(contents.get("value", ""))
        if isinstance(contents, list):
            return "\n".join(
                c.get("value", "") if isinstance(c, dict) else str(c) for c in contents
            )
        return str(contents or "")


def _normalize_uri(uri: str) -> str:
    """Servers may encode drive letters differently (file:///c%3A/ vs file:///C:/)."""
    try:
        return path_to_uri(uri_to_path(uri)) if uri.startswith("file:") else uri
    except (ValueError, OSError):
        return uri


# ------------------------------------------------------------------ manager


@dataclass
class LSPManager:
    """Starts language servers on demand and keeps them for the session."""

    root: Path
    settings: Any = None
    _clients: Dict[str, Optional[LSPClient]] = field(default_factory=dict)
    _lock: threading.Lock = field(default_factory=threading.Lock)

    @property
    def enabled(self) -> bool:
        return self.settings is not False

    def client_for(self, path: Path) -> Optional[Tuple[LSPClient, str]]:
        """(client, languageId) for the file, starting the server if needed."""
        if not self.enabled:
            return None
        language = language_for(path)
        if language is None:
            return None
        language_id = LANGUAGES[language][0][path.suffix.lower()]
        with self._lock:
            if language not in self._clients:
                self._clients[language] = self._start(language)
            client = self._clients[language]
            if client is not None and not client.alive:
                self._clients[language] = client = self._start(language)
        return (client, language_id) if client else None

    def _start(self, language: str) -> Optional[LSPClient]:
        argv = find_command(language, self.settings)
        if argv is None:
            return None
        client = LSPClient(argv, self.root, language)
        try:
            client.start()
        except LSPError as e:
            logger.warning(f"Language server for {language} failed to start: {e}")
            client.stop()
            return None
        return client

    def diagnostics(self, path: Path, errors_only: bool = True) -> Optional[List[Diagnostic]]:
        """Diagnostics for an edited file, or None when no server handles it."""
        found = self.client_for(path)
        if found is None:
            return None
        client, language_id = found
        try:
            items = client.diagnostics(path, language_id)
        except (LSPError, OSError) as e:
            logger.warning(f"Language server diagnostics failed for {path}: {e}")
            return None
        return [d for d in items if d.severity == "error"] if errors_only else items

    def status(self) -> Dict[str, str]:
        """language -> 'running <cmd>' / 'available <cmd>' / 'not installed'."""
        result = {}
        for language in LANGUAGES:
            client = self._clients.get(language)
            if client is not None and client.alive:
                result[language] = f"running {client.argv[0]}"
                continue
            argv = find_command(language, self.settings) if self.enabled else None
            result[language] = f"available {argv[0]}" if argv else "not installed"
        return result

    def stop(self) -> None:
        for client in self._clients.values():
            if client is not None:
                client.stop()
        self._clients.clear()


_manager: Optional[LSPManager] = None


def get_lsp_manager(root: Optional[Path] = None) -> LSPManager:
    """The session's manager (created on first use for the working directory)."""
    global _manager
    if _manager is None:
        try:
            from joshu.core.config import get_config_manager

            settings = get_config_manager().get("lsp")
        except Exception:
            settings = None
        _manager = LSPManager(root=(root or Path.cwd()), settings=settings)
        atexit.register(_manager.stop)
    return _manager


def reset_lsp_manager() -> None:
    """Stop servers and forget the manager (tests, settings changes)."""
    global _manager
    if _manager is not None:
        _manager.stop()
    _manager = None
