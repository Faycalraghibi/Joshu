"""
Tests for IDE CLI Commands.
"""

from unittest.mock import MagicMock, patch

from joshu.commands.ide import ide_context, ide_install, ide_start, ide_status
from joshu.commands.types import ErrorActionReturn, MessageActionReturn


class TestIdeStatus:
    """Tests for ide_status command."""

    @patch("joshu.commands.ide.discover_ide_servers")
    def test_no_servers(self, mock_discover):
        """Should report no servers running."""
        mock_discover.return_value = []

        result = ide_status()

        assert isinstance(result, MessageActionReturn)
        assert "No IDE servers running" in result.message

    @patch("joshu.commands.ide.discover_ide_servers")
    def test_with_servers(self, mock_discover):
        """Should list running servers."""
        mock_server = MagicMock()
        mock_server.port = 8080
        mock_server.workspace_path = "/workspace"
        mock_server.is_alive.return_value = True
        mock_discover.return_value = [mock_server]

        result = ide_status()

        assert isinstance(result, MessageActionReturn)
        assert "8080" in result.message


class TestIdeContext:
    """Tests for ide_context command."""

    @patch("joshu.commands.ide.get_ide_client")
    def test_no_client(self, mock_get_client):
        """Should report no server when client unavailable."""
        mock_get_client.return_value = None

        result = ide_context()

        assert isinstance(result, MessageActionReturn)
        assert "No IDE server connected" in result.message

    @patch("joshu.commands.ide.get_ide_client")
    def test_context_failure(self, mock_get_client):
        """Should handle context fetch failure."""
        mock_client = MagicMock()
        mock_client.get_context.return_value = None
        mock_get_client.return_value = mock_client

        result = ide_context()

        assert isinstance(result, ErrorActionReturn)

    @patch("joshu.commands.ide.get_ide_client")
    def test_shows_context(self, mock_get_client):
        """Should display context information."""
        from joshu.ide.schemas import CursorPosition, IdeContext

        mock_context = IdeContext(
            workspace_path="/workspace",
            active_file="main.py",
            cursor_position=CursorPosition(line=10, column=5),
            selected_text="hello",
            recent_files=[],
        )
        mock_client = MagicMock()
        mock_client.get_context.return_value = mock_context
        mock_get_client.return_value = mock_client

        result = ide_context()

        assert isinstance(result, MessageActionReturn)
        assert "/workspace" in result.message
        assert "main.py" in result.message


class TestIdeStart:
    """Tests for ide_start command."""

    @patch("joshu.ide.server.get_ide_server")
    def test_already_running(self, mock_get_server):
        """Should report if already running."""
        mock_server = MagicMock()
        mock_server.is_running = True
        mock_server.port = 8080
        mock_get_server.return_value = mock_server

        result = ide_start()

        assert isinstance(result, MessageActionReturn)
        assert "already running" in result.message

    @patch("joshu.ide.server.get_ide_server")
    def test_starts_server(self, mock_get_server):
        """Should start server and report port."""
        mock_server = MagicMock()
        mock_server.is_running = False
        mock_server.config.workspace_path = ""

        # Setup async mock
        async def mock_start():
            return 8080

        mock_server.start = mock_start
        mock_get_server.return_value = mock_server

        result = ide_start()

        assert isinstance(result, MessageActionReturn)
        assert "8080" in result.message


class TestIdeInstall:
    """Tests for ide_install command."""

    @patch("joshu.commands.ide.subprocess.run")
    def test_vscode_not_found(self, mock_run):
        """Should report when VS Code CLI not found."""
        mock_run.side_effect = Exception("not found")

        result = ide_install()

        assert isinstance(result, MessageActionReturn)
        assert "not found" in result.message.lower() or "manually" in result.message.lower()
