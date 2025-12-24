"""
Tests for IDE Discovery.
"""

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

from joshu.ide.discovery import (
    IDEServerInfo,
    discover_ide_servers,
    find_server_for_workspace,
    get_default_server,
)


class TestIDEServerInfo:
    """Tests for IDEServerInfo dataclass."""

    def test_fields(self):
        """Should have required fields."""
        info = IDEServerInfo(
            port=8080,
            token="test-token",
            workspace_path="/workspace",
            pid=1234,
            info_file=Path("/tmp/test.json"),
        )

        assert info.port == 8080
        assert info.token == "test-token"
        assert info.workspace_path == "/workspace"
        assert info.pid == 1234

    @patch("joshu.ide.discovery.httpx.get")
    def test_is_alive_success(self, mock_get):
        """Should return True when server responds."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_get.return_value = mock_response

        info = IDEServerInfo(
            port=8080,
            token="test",
            workspace_path="",
            pid=1234,
            info_file=Path("/tmp/test.json"),
        )

        assert info.is_alive() is True

    @patch("joshu.ide.discovery.httpx.get")
    def test_is_alive_failure(self, mock_get):
        """Should return False when server fails to respond."""
        mock_get.side_effect = Exception("Connection refused")

        info = IDEServerInfo(
            port=8080,
            token="test",
            workspace_path="",
            pid=1234,
            info_file=Path("/tmp/test.json"),
        )

        assert info.is_alive() is False


class TestDiscoverServers:
    """Tests for discover_ide_servers function."""

    def test_no_servers(self):
        """Should return empty list when no servers found."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("tempfile.gettempdir", return_value=tmpdir):
                servers = discover_ide_servers()
                assert servers == []

    def test_finds_server_files(self):
        """Should find and parse server info files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create server info file
            info_file = Path(tmpdir) / "joshu-ide-server-1234-8080.json"
            info_file.write_text(
                json.dumps(
                    {
                        "port": 8080,
                        "token": "test-token",
                        "workspace_path": "/workspace",
                        "pid": 1234,
                    }
                )
            )

            with patch("tempfile.gettempdir", return_value=tmpdir):
                with patch.object(IDEServerInfo, "is_alive", return_value=True):
                    servers = discover_ide_servers()
                    assert len(servers) == 1
                    assert servers[0].port == 8080
                    assert servers[0].token == "test-token"

    def test_removes_stale_files(self):
        """Should remove info files for dead servers."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create server info file
            info_file = Path(tmpdir) / "joshu-ide-server-1234-8080.json"
            info_file.write_text(
                json.dumps(
                    {
                        "port": 8080,
                        "token": "test-token",
                        "workspace_path": "/workspace",
                        "pid": 1234,
                    }
                )
            )

            with patch("tempfile.gettempdir", return_value=tmpdir):
                with patch.object(IDEServerInfo, "is_alive", return_value=False):
                    servers = discover_ide_servers()
                    assert servers == []
                    # File should be removed
                    assert not info_file.exists()


class TestFindServerForWorkspace:
    """Tests for find_server_for_workspace function."""

    @patch("joshu.ide.discovery.discover_ide_servers")
    def test_finds_matching_workspace(self, mock_discover):
        """Should find server for matching workspace."""
        server = IDEServerInfo(
            port=8080,
            token="test",
            workspace_path="/my/workspace",
            pid=1234,
            info_file=Path("/tmp/test.json"),
        )
        mock_discover.return_value = [server]

        result = find_server_for_workspace("/my/workspace")

        assert result == server

    @patch("joshu.ide.discovery.discover_ide_servers")
    def test_returns_any_if_no_match(self, mock_discover):
        """Should return first server if no workspace match."""
        server = IDEServerInfo(
            port=8080,
            token="test",
            workspace_path="/other/workspace",
            pid=1234,
            info_file=Path("/tmp/test.json"),
        )
        mock_discover.return_value = [server]

        result = find_server_for_workspace("/my/workspace")

        assert result == server

    @patch("joshu.ide.discovery.discover_ide_servers")
    def test_returns_none_if_no_servers(self, mock_discover):
        """Should return None if no servers found."""
        mock_discover.return_value = []

        result = find_server_for_workspace("/my/workspace")

        assert result is None


class TestGetDefaultServer:
    """Tests for get_default_server function."""

    @patch("joshu.ide.discovery.discover_ide_servers")
    def test_returns_first_server(self, mock_discover):
        """Should return first available server."""
        server = IDEServerInfo(
            port=8080,
            token="test",
            workspace_path="",
            pid=1234,
            info_file=Path("/tmp/test.json"),
        )
        mock_discover.return_value = [server]

        result = get_default_server()

        assert result == server

    @patch("joshu.ide.discovery.discover_ide_servers")
    def test_returns_none_if_empty(self, mock_discover):
        """Should return None if no servers."""
        mock_discover.return_value = []

        result = get_default_server()

        assert result is None
