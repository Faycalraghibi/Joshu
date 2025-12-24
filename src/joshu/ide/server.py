"""
IDE Server.

Python-based HTTP server for IDE integration.
Receives context updates from VS Code extension and manages diffs.
"""

from __future__ import annotations

import json
import logging
import os
import secrets
import tempfile
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)

# Default server configuration
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 0  # Dynamic port assignment


@dataclass
class ServerConfig:
    """IDE server configuration."""

    host: str = DEFAULT_HOST
    port: int = DEFAULT_PORT
    token: str = field(default_factory=lambda: secrets.token_urlsafe(32))
    workspace_path: str = ""


@dataclass
class IdeContext:
    """Current IDE context."""

    workspace_path: str = ""
    recent_files: List[Dict[str, Any]] = field(default_factory=list)
    active_file: Optional[str] = None
    cursor_line: int = 0
    cursor_column: int = 0
    selected_text: str = ""
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "workspace_path": self.workspace_path,
            "recent_files": self.recent_files,
            "active_file": self.active_file,
            "cursor_position": {"line": self.cursor_line, "column": self.cursor_column},
            "selected_text": self.selected_text,
            "updated_at": self.updated_at,
        }


@dataclass
class DiffProposal:
    """A proposed file modification."""

    proposal_id: str
    file_path: str
    original_content: str
    proposed_content: str
    description: str = ""
    status: str = "pending"  # pending, accepted, rejected
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())


class IDEServer:
    """
    Python-based IDE server.

    Provides HTTP endpoints for:
    - Receiving context updates from VS Code
    - Managing diff proposals
    - Serving IDE state to Joshu CLI
    """

    def __init__(self, config: Optional[ServerConfig] = None):
        """Initialize the IDE server."""
        self.config = config or ServerConfig()
        self.context = IdeContext()
        self.proposals: Dict[str, DiffProposal] = {}
        self._server = None
        self._port: int = 0
        self._running = False
        self._callbacks: Dict[str, List[Callable]] = {
            "context_update": [],
            "diff_accepted": [],
            "diff_rejected": [],
        }

    @property
    def port(self) -> int:
        """Get the server port."""
        return self._port

    @property
    def is_running(self) -> bool:
        """Check if server is running."""
        return self._running

    def on(self, event: str, callback: Callable) -> None:
        """Register an event callback."""
        if event in self._callbacks:
            self._callbacks[event].append(callback)

    def _emit(self, event: str, data: Any = None) -> None:
        """Emit an event to callbacks."""
        for callback in self._callbacks.get(event, []):
            try:
                callback(data)
            except Exception as e:
                logger.error(f"Callback error for {event}: {e}")

    async def start(self) -> int:
        """
        Start the IDE server.

        Returns:
            The port the server is listening on.
        """
        # Use built-in HTTP server (no aiohttp dependency)
        return await self._start_basic_server()

    async def _start_basic_server(self) -> int:
        """Start a basic HTTP server."""
        import http.server
        import socketserver
        import threading

        server_instance = self

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_POST(self):
                # Basic token check
                auth = self.headers.get("Authorization", "")
                if not auth.startswith("Bearer ") or auth[7:] != server_instance.config.token:
                    self.send_response(401)
                    self.end_headers()
                    return

                content_length = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(content_length).decode("utf-8")

                try:
                    data = json.loads(body) if body else {}
                except json.JSONDecodeError:
                    data = {}

                if self.path == "/context":
                    server_instance._update_context(data)
                    response = {"status": "ok"}
                elif self.path == "/diff/propose":
                    proposal = DiffProposal(
                        proposal_id=secrets.token_urlsafe(8),
                        file_path=data.get("file_path", ""),
                        original_content=data.get("original_content", ""),
                        proposed_content=data.get("proposed_content", ""),
                        description=data.get("description", ""),
                    )
                    server_instance.proposals[proposal.proposal_id] = proposal
                    response = {"proposal_id": proposal.proposal_id}
                elif self.path.startswith("/diff/") and self.path.endswith("/accept"):
                    proposal_id = self.path.split("/")[2]
                    server_instance._accept_diff(proposal_id)
                    response = {"status": "accepted"}
                elif self.path.startswith("/diff/") and self.path.endswith("/reject"):
                    proposal_id = self.path.split("/")[2]
                    server_instance._reject_diff(proposal_id)
                    response = {"status": "rejected"}
                else:
                    response = {"error": "not found"}

                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps(response).encode())

            def do_GET(self):
                if self.path == "/context":
                    response = server_instance.context.to_dict()
                elif self.path == "/health":
                    response = {"status": "healthy", "port": server_instance._port}
                elif self.path == "/diff/pending":
                    response = {
                        "proposals": [
                            {
                                "proposal_id": p.proposal_id,
                                "file_path": p.file_path,
                                "description": p.description,
                                "status": p.status,
                            }
                            for p in server_instance.proposals.values()
                            if p.status == "pending"
                        ]
                    }
                else:
                    response = {"error": "not found"}

                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps(response).encode())

            def log_message(self, format, *args):
                pass  # Suppress logging

        # Find available port
        server = socketserver.TCPServer((self.config.host, 0), Handler)
        self._port = server.server_address[1]
        self._running = True
        self._server = server

        # Write server info
        self._write_server_info()

        # Run in thread
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()

        logger.info(f"IDE server started on {self.config.host}:{self._port}")
        return self._port

    def _update_context(self, data: Dict[str, Any]) -> None:
        """Update IDE context from incoming data."""
        if "workspace_path" in data:
            self.context.workspace_path = data["workspace_path"]
        if "recent_files" in data:
            self.context.recent_files = data["recent_files"][:10]  # Limit to 10
        if "active_file" in data:
            self.context.active_file = data["active_file"]
        if "cursor_position" in data:
            pos = data["cursor_position"]
            self.context.cursor_line = pos.get("line", 0)
            self.context.cursor_column = pos.get("column", 0)
        if "selected_text" in data:
            # Limit selected text to 16KB
            self.context.selected_text = data["selected_text"][:16384]

        self.context.updated_at = datetime.now().isoformat()
        self._emit("context_update", self.context)

    def _accept_diff(self, proposal_id: str) -> None:
        """Accept a diff proposal."""
        if proposal_id in self.proposals:
            self.proposals[proposal_id].status = "accepted"
            self._emit("diff_accepted", self.proposals[proposal_id])

    def _reject_diff(self, proposal_id: str) -> None:
        """Reject a diff proposal."""
        if proposal_id in self.proposals:
            self.proposals[proposal_id].status = "rejected"
            self._emit("diff_rejected", self.proposals[proposal_id])

    def _write_server_info(self) -> None:
        """Write server info to temp file for discovery."""
        info = {
            "port": self._port,
            "token": self.config.token,
            "workspace_path": self.config.workspace_path,
            "pid": os.getpid(),
        }

        # Write to temp directory
        temp_dir = Path(tempfile.gettempdir())
        info_file = temp_dir / f"joshu-ide-server-{os.getpid()}-{self._port}.json"

        try:
            info_file.write_text(json.dumps(info))
            # Restrict permissions (Unix only)
            if os.name != "nt":
                os.chmod(info_file, 0o600)
            logger.debug(f"Server info written to {info_file}")
        except Exception as e:
            logger.warning(f"Failed to write server info: {e}")

    async def stop(self) -> None:
        """Stop the IDE server."""
        self._running = False
        if self._server:
            self._server.shutdown()
        # Clean up info file
        temp_dir = Path(tempfile.gettempdir())
        info_file = temp_dir / f"joshu-ide-server-{os.getpid()}-{self._port}.json"
        try:
            info_file.unlink(missing_ok=True)
        except Exception:
            pass
        logger.info("IDE server stopped")


# Global server instance
_server: Optional[IDEServer] = None


def get_ide_server() -> IDEServer:
    """Get the global IDE server instance."""
    global _server
    if _server is None:
        _server = IDEServer()
    return _server


async def start_ide_server(workspace_path: str = "") -> int:
    """Start the global IDE server."""
    server = get_ide_server()
    server.config.workspace_path = workspace_path
    return await server.start()
