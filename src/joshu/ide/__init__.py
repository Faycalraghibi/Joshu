"""
IDE Integration Package.

Provides IDE integration capabilities for Joshu CLI.
"""

from joshu.ide.client import IDEClient, get_current_ide_context, get_ide_client
from joshu.ide.diff_manager import DiffManager, DiffProposal, get_diff_manager
from joshu.ide.discovery import (
    IDEServerInfo,
    discover_ide_servers,
    find_server_for_workspace,
    get_default_server,
)
from joshu.ide.schemas import (
    CursorPosition,
    DiffAction,
    FileInfo,
    IdeContext,
)
from joshu.ide.server import IDEServer, get_ide_server, start_ide_server

__all__ = [
    # Schemas
    "CursorPosition",
    "FileInfo",
    "IdeContext",
    "DiffAction",
    # Server
    "IDEServer",
    "get_ide_server",
    "start_ide_server",
    # Discovery
    "IDEServerInfo",
    "discover_ide_servers",
    "find_server_for_workspace",
    "get_default_server",
    # Client
    "IDEClient",
    "get_ide_client",
    "get_current_ide_context",
    # Diff Manager
    "DiffManager",
    "DiffProposal",
    "get_diff_manager",
]
