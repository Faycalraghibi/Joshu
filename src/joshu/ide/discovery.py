"""
IDE Discovery.

Finds running IDE server instances.
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

import httpx

logger = logging.getLogger(__name__)


@dataclass
class IDEServerInfo:
    """Information about a running IDE server."""

    port: int
    token: str
    workspace_path: str
    pid: int
    info_file: Path

    def is_alive(self) -> bool:
        """Check if the server is still running."""
        try:
            response = httpx.get(
                f"http://127.0.0.1:{self.port}/health",
                timeout=2.0,
            )
            return response.status_code == 200
        except Exception:
            return False


def discover_ide_servers() -> List[IDEServerInfo]:
    """
    Discover running IDE server instances.

    Scans temp directory for server info files.

    Returns:
        List of running IDE servers.
    """
    servers = []
    temp_dir = Path(tempfile.gettempdir())

    for info_file in temp_dir.glob("joshu-ide-server-*.json"):
        try:
            data = json.loads(info_file.read_text())
            server = IDEServerInfo(
                port=data["port"],
                token=data["token"],
                workspace_path=data.get("workspace_path", ""),
                pid=data.get("pid", 0),
                info_file=info_file,
            )

            # Verify server is still running
            if server.is_alive():
                servers.append(server)
            else:
                # Clean up stale info file
                try:
                    info_file.unlink()
                except Exception:
                    pass

        except Exception as e:
            logger.debug(f"Failed to read server info {info_file}: {e}")

    return servers


def find_server_for_workspace(workspace_path: str) -> Optional[IDEServerInfo]:
    """
    Find an IDE server for a specific workspace.

    Args:
        workspace_path: Path to the workspace.

    Returns:
        IDEServerInfo if found, None otherwise.
    """
    workspace_path = os.path.abspath(workspace_path)
    servers = discover_ide_servers()

    for server in servers:
        if server.workspace_path and os.path.abspath(server.workspace_path) == workspace_path:
            return server

    # If no exact match, return any server
    return servers[0] if servers else None


def get_default_server() -> Optional[IDEServerInfo]:
    """
    Get the default IDE server.

    Returns the first available server.

    Returns:
        IDEServerInfo if found, None otherwise.
    """
    servers = discover_ide_servers()
    return servers[0] if servers else None
