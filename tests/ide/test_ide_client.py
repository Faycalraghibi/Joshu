"""
Tests for IDE Client.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from joshu.ide.client import (
    IDEClient,
    get_current_ide_context,
    get_ide_client,
)
from joshu.ide.discovery import IDEServerInfo
from joshu.ide.schemas import IdeContext


class TestIDEClient:
    """Tests for IDEClient."""

    @pytest.fixture
    def server_info(self):
        """Create mock server info."""
        return IDEServerInfo(
            port=8080,
            token="test-token",
            workspace_path="/workspace",
            pid=1234,
            info_file=Path("/tmp/test.json"),
        )

    @pytest.fixture
    def client(self, server_info):
        """Create IDE client."""
        return IDEClient(server_info=server_info)

    def test_base_url(self, client):
        """Should construct correct base URL."""
        assert client.base_url == "http://127.0.0.1:8080"

    def test_headers_include_auth(self, client):
        """Should include bearer token in headers."""
        headers = client.headers
        assert headers["Authorization"] == "Bearer test-token"
        assert headers["Content-Type"] == "application/json"

    @patch("joshu.ide.client.httpx.get")
    def test_get_context_success(self, mock_get, client):
        """Should parse context response."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "workspace_path": "/test",
            "active_file": "main.py",
            "cursor_position": {"line": 10, "column": 5},
            "selected_text": "hello",
            "recent_files": [],
        }
        mock_get.return_value = mock_response

        context = client.get_context()

        assert context is not None
        assert context.workspace_path == "/test"
        assert context.active_file == "main.py"

    @patch("joshu.ide.client.httpx.get")
    def test_get_context_failure(self, mock_get, client):
        """Should return None on failure."""
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_get.return_value = mock_response

        context = client.get_context()

        assert context is None

    @patch("joshu.ide.client.httpx.get")
    def test_get_context_exception(self, mock_get, client):
        """Should handle exceptions gracefully."""
        mock_get.side_effect = Exception("Connection failed")

        context = client.get_context()

        assert context is None

    @patch("joshu.ide.client.httpx.post")
    def test_propose_diff_success(self, mock_post, client):
        """Should return proposal ID on success."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"proposal_id": "abc123"}
        mock_post.return_value = mock_response

        proposal_id = client.propose_diff(
            file_path="/test.py",
            original_content="old",
            proposed_content="new",
            description="test change",
        )

        assert proposal_id == "abc123"
        mock_post.assert_called_once()

    @patch("joshu.ide.client.httpx.post")
    def test_propose_diff_failure(self, mock_post, client):
        """Should return None on failure."""
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_post.return_value = mock_response

        proposal_id = client.propose_diff(
            file_path="/test.py",
            original_content="old",
            proposed_content="new",
        )

        assert proposal_id is None

    @patch("joshu.ide.client.httpx.get")
    def test_get_pending_diffs(self, mock_get, client):
        """Should return pending proposals."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "proposals": [
                {"proposal_id": "1", "status": "pending"},
                {"proposal_id": "2", "status": "pending"},
            ]
        }
        mock_get.return_value = mock_response

        proposals = client.get_pending_diffs()

        assert len(proposals) == 2

    @patch("joshu.ide.client.httpx.get")
    def test_is_connected_true(self, mock_get, client):
        """Should return True when server responds."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_get.return_value = mock_response

        assert client.is_connected() is True

    @patch("joshu.ide.client.httpx.get")
    def test_is_connected_false(self, mock_get, client):
        """Should return False when server fails."""
        mock_get.side_effect = Exception("Connection refused")

        assert client.is_connected() is False


class TestGetIdeClient:
    """Tests for get_ide_client function."""

    @patch("joshu.ide.client.get_default_server")
    def test_returns_client_when_server_found(self, mock_get_server):
        """Should return client when server is available."""
        mock_server = IDEServerInfo(
            port=8080,
            token="test",
            workspace_path="",
            pid=1234,
            info_file=Path("/tmp/test.json"),
        )
        mock_get_server.return_value = mock_server

        client = get_ide_client()

        assert client is not None
        assert isinstance(client, IDEClient)

    @patch("joshu.ide.client.get_default_server")
    def test_returns_none_when_no_server(self, mock_get_server):
        """Should return None when no server available."""
        mock_get_server.return_value = None

        client = get_ide_client()

        assert client is None


class TestGetCurrentIdeContext:
    """Tests for get_current_ide_context function."""

    @patch("joshu.ide.client.get_ide_client")
    def test_returns_context(self, mock_get_client):
        """Should return context from client."""
        mock_client = MagicMock()
        mock_context = IdeContext(workspace_path="/test")
        mock_client.get_context.return_value = mock_context
        mock_get_client.return_value = mock_client

        context = get_current_ide_context()

        assert context == mock_context

    @patch("joshu.ide.client.get_ide_client")
    def test_returns_none_when_no_client(self, mock_get_client):
        """Should return None when no client available."""
        mock_get_client.return_value = None

        context = get_current_ide_context()

        assert context is None
