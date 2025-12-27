"""
Tests for MCP command handlers.
"""

from unittest.mock import AsyncMock, MagicMock, patch

from joshu.commands.mcp import (
    MCPAddConfig,
    mcp_add,
    mcp_connect,
    mcp_list,
    mcp_remove,
    mcp_status,
)
from joshu.commands.types import ErrorActionReturn, MessageActionReturn


class TestMCPAdd:
    """Tests for mcp_add command."""

    @patch("joshu.commands.mcp.get_mcp_registry")
    def test_add_stdio_server(self, mock_get_registry):
        """Should add a stdio server successfully."""
        mock_registry = MagicMock()
        mock_get_registry.return_value = mock_registry

        config = MCPAddConfig(
            name="test-server",
            command="node server.js",
            args=["--port", "3000"],
        )

        result = mcp_add(config)

        assert isinstance(result, MessageActionReturn)
        assert "Added MCP server" in result.message
        assert "test-server" in result.message
        mock_registry.add_server.assert_called_once()

    @patch("joshu.commands.mcp.get_mcp_registry")
    def test_add_http_server(self, mock_get_registry):
        """Should add an HTTP server successfully."""
        mock_registry = MagicMock()
        mock_get_registry.return_value = mock_registry

        config = MCPAddConfig(
            name="http-server",
            url="http://localhost:8080/mcp",
        )

        result = mcp_add(config)

        assert isinstance(result, MessageActionReturn)
        assert "Added MCP server" in result.message

    def test_add_no_command_or_url(self):
        """Should fail when neither command nor URL provided."""
        config = MCPAddConfig(name="empty-server")

        result = mcp_add(config)

        assert isinstance(result, ErrorActionReturn)
        assert "Must specify" in result.error_message


class TestMCPList:
    """Tests for mcp_list command."""

    @patch("joshu.commands.mcp.get_mcp_registry")
    def test_list_empty(self, mock_get_registry):
        """Should handle no servers."""
        mock_registry = MagicMock()
        mock_registry.list_servers.return_value = []
        mock_get_registry.return_value = mock_registry

        result = mcp_list()

        assert isinstance(result, MessageActionReturn)
        assert "No MCP servers" in result.message

    @patch("joshu.commands.mcp.get_mcp_registry")
    def test_list_with_servers(self, mock_get_registry):
        """Should list configured servers."""
        mock_server = MagicMock()
        mock_server.name = "test-server"
        mock_server.enabled = True
        mock_server.transport.value = "stdio"
        mock_server.command = "node server.js"
        mock_server.url = None
        mock_server.to_dict.return_value = {"name": "test-server"}

        mock_registry = MagicMock()
        mock_registry.list_servers.return_value = [mock_server]
        mock_registry.is_connected.return_value = False
        mock_get_registry.return_value = mock_registry

        result = mcp_list()

        assert isinstance(result, MessageActionReturn)
        assert "test-server" in result.message


class TestMCPRemove:
    """Tests for mcp_remove command."""

    @patch("joshu.commands.mcp.get_mcp_registry")
    def test_remove_success(self, mock_get_registry):
        """Should remove server successfully."""
        mock_registry = MagicMock()
        mock_registry.get_server.return_value = MagicMock()
        mock_registry.is_connected.return_value = False
        mock_get_registry.return_value = mock_registry

        result = mcp_remove("test-server")

        assert isinstance(result, MessageActionReturn)
        assert "Removed" in result.message
        mock_registry.remove_server.assert_called_once_with("test-server")

    @patch("joshu.commands.mcp.get_mcp_registry")
    def test_remove_not_found(self, mock_get_registry):
        """Should fail for non-existent server."""
        mock_registry = MagicMock()
        mock_registry.get_server.return_value = None
        mock_get_registry.return_value = mock_registry

        result = mcp_remove("non-existent")

        assert isinstance(result, ErrorActionReturn)
        assert "not found" in result.error_message


class TestMCPStatus:
    """Tests for mcp_status command."""

    @patch("joshu.commands.mcp.get_mcp_registry")
    def test_status_empty(self, mock_get_registry):
        """Should handle no servers."""
        mock_registry = MagicMock()
        mock_registry.get_status.return_value = {}
        mock_get_registry.return_value = mock_registry

        result = mcp_status()

        assert isinstance(result, MessageActionReturn)
        assert "No MCP servers" in result.message

    @patch("joshu.commands.mcp.get_mcp_registry")
    def test_status_with_servers(self, mock_get_registry):
        """Should show server status."""
        mock_registry = MagicMock()
        mock_registry.get_status.return_value = {
            "test-server": {
                "connected": True,
                "enabled": True,
                "transport": "stdio",
                "tool_count": 5,
            }
        }
        mock_get_registry.return_value = mock_registry

        result = mcp_status()

        assert isinstance(result, MessageActionReturn)
        assert "test-server" in result.message
        assert "Connected" in result.message


class TestMCPConnect:
    """Tests for mcp_connect command."""

    @patch("joshu.commands.mcp.get_mcp_registry")
    def test_connect_success(self, mock_get_registry):
        """Should connect successfully."""
        mock_registry = MagicMock()
        mock_registry.get_server.return_value = MagicMock()
        mock_registry.is_connected.return_value = False
        # connect_server is async, so use AsyncMock
        mock_registry.connect_server = AsyncMock(return_value=True)
        mock_get_registry.return_value = mock_registry

        result = mcp_connect("test-server")

        assert isinstance(result, MessageActionReturn)
        assert "Connected" in result.message

    @patch("joshu.commands.mcp.get_mcp_registry")
    def test_connect_not_found(self, mock_get_registry):
        """Should fail for non-existent server."""
        mock_registry = MagicMock()
        mock_registry.get_server.return_value = None
        mock_get_registry.return_value = mock_registry

        result = mcp_connect("non-existent")

        assert isinstance(result, ErrorActionReturn)
        assert "not found" in result.error_message
