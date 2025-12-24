"""
IDE CLI Command Handlers.

Provides CLI commands for managing IDE integration:
- joshu ide status - Show IDE connection status
- joshu ide context - Display current IDE context
- joshu ide install - Install VS Code extension
- joshu ide start - Start IDE server
"""

from __future__ import annotations

import asyncio
import logging
import os
import subprocess
from pathlib import Path
from typing import Optional

from joshu.commands.types import (
    CommandActionReturn,
    ErrorActionReturn,
    MessageActionReturn,
)
from joshu.ide.client import get_ide_client
from joshu.ide.discovery import discover_ide_servers

logger = logging.getLogger(__name__)


def ide_status() -> CommandActionReturn:
    """
    Show IDE connection status.

    Returns:
        CommandActionReturn with status info.
    """
    try:
        servers = discover_ide_servers()

        if not servers:
            return MessageActionReturn(
                message="**IDE Status:** No IDE servers running\n\nStart with: `joshu ide start`",
                message_type="info",
            )

        lines = ["**IDE Status:**", ""]
        for server in servers:
            status = "🟢 Connected" if server.is_alive() else "🔴 Disconnected"
            lines.append(f"  {status} Port {server.port}")
            if server.workspace_path:
                lines.append(f"      📁 {server.workspace_path}")

        return MessageActionReturn(
            message="\n".join(lines),
            message_type="success",
            metadata={"servers": len(servers)},
        )

    except Exception as e:
        logger.error(f"IDE status failed: {e}")
        return ErrorActionReturn(
            error_message=f"Failed to get IDE status: {e}",
            error_code="IDE_STATUS_FAILED",
            recoverable=True,
        )


def ide_context() -> CommandActionReturn:
    """
    Display current IDE context.

    Returns:
        CommandActionReturn with context info.
    """
    try:
        client = get_ide_client()
        if not client:
            return MessageActionReturn(
                message="No IDE server connected. Start with: `joshu ide start`",
                message_type="warning",
            )

        context = client.get_context()
        if not context:
            return ErrorActionReturn(
                error_message="Failed to get IDE context",
                error_code="CONTEXT_FAILED",
                recoverable=True,
            )

        lines = ["**IDE Context:**", ""]

        if context.workspace_path:
            lines.append(f"📁 **Workspace:** {context.workspace_path}")

        if context.active_file:
            lines.append(f"📄 **Active File:** {context.active_file}")
            if context.cursor_position:
                pos = context.cursor_position
                lines.append(f"📍 **Cursor:** Line {pos.line}, Column {pos.column}")

        if context.recent_files:
            lines.append("")
            lines.append("**Recent Files:**")
            for f in context.recent_files[:5]:
                name = Path(f.path).name if hasattr(f, "path") else f.get("path", "")
                lines.append(f"  • {name}")

        if context.selected_text:
            lines.append("")
            preview = context.selected_text[:100]
            if len(context.selected_text) > 100:
                preview += "..."
            lines.append(f"**Selection:** `{preview}`")

        return MessageActionReturn(
            message="\n".join(lines),
            message_type="info",
            metadata={"context": context.to_dict()},
        )

    except Exception as e:
        logger.error(f"IDE context failed: {e}")
        return ErrorActionReturn(
            error_message=f"Failed to get IDE context: {e}",
            error_code="CONTEXT_FAILED",
            recoverable=True,
        )


def ide_start(workspace_path: Optional[str] = None) -> CommandActionReturn:
    """
    Start the IDE server.

    Args:
        workspace_path: Optional workspace path.

    Returns:
        CommandActionReturn with result.
    """
    try:
        from joshu.ide.server import get_ide_server

        server = get_ide_server()

        if server.is_running:
            return MessageActionReturn(
                message=f"IDE server already running on port {server.port}",
                message_type="info",
            )

        workspace = workspace_path or os.getcwd()
        server.config.workspace_path = workspace

        # Run in background
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        port = loop.run_until_complete(server.start())

        return MessageActionReturn(
            message=f"✓ IDE server started on port {port}\n\nWorkspace: {workspace}",
            message_type="success",
            metadata={"port": port, "workspace": workspace},
        )

    except Exception as e:
        logger.error(f"IDE start failed: {e}")
        return ErrorActionReturn(
            error_message=f"Failed to start IDE server: {e}",
            error_code="START_FAILED",
            recoverable=True,
        )


def ide_install() -> CommandActionReturn:
    """
    Install the VS Code extension.

    Returns:
        CommandActionReturn with result.
    """
    try:
        # Check if VS Code CLI is available
        vscode_cli = None
        for cmd in ["code", "code-insiders"]:
            try:
                result = subprocess.run(
                    [cmd, "--version"],
                    capture_output=True,
                    timeout=5,
                )
                if result.returncode == 0:
                    vscode_cli = cmd
                    break
            except Exception:
                continue

        if not vscode_cli:
            return MessageActionReturn(
                message="VS Code CLI not found.\n\n"
                "Install manually:\n"
                "1. Open VS Code\n"
                "2. Go to Extensions (Ctrl+Shift+X)\n"
                "3. Search for 'Joshu IDE Companion'\n"
                "4. Click Install",
                message_type="warning",
            )

        # Get extension path
        extension_path = (
            Path(__file__).parent.parent.parent.parent / "packages" / "vscode-joshu-companion"
        )

        if extension_path.exists():
            # Install from local path
            result = subprocess.run(
                [vscode_cli, "--install-extension", str(extension_path)],
                capture_output=True,
                text=True,
                timeout=60,
            )

            if result.returncode == 0:
                return MessageActionReturn(
                    message="✓ Joshu IDE Companion extension installed!\n\n"
                    "Restart VS Code to activate.",
                    message_type="success",
                )
            else:
                stderr_msg = result.stderr if isinstance(result.stderr, str) else str(result.stderr)
                return ErrorActionReturn(
                    error_message=f"Installation failed: {stderr_msg}",
                    error_code="INSTALL_FAILED",
                    recoverable=True,
                )
        else:
            return MessageActionReturn(
                message="Extension package not found.\n\n"
                "Install from marketplace:\n"
                "1. Open VS Code Extensions\n"
                "2. Search 'Joshu IDE Companion'\n"
                "3. Click Install",
                message_type="info",
            )

    except Exception as e:
        logger.error(f"IDE install failed: {e}")
        return ErrorActionReturn(
            error_message=f"Installation failed: {e}",
            error_code="INSTALL_FAILED",
            recoverable=True,
        )
