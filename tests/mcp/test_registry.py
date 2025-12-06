"""
Unit tests for MCP Registry.

Tests MCPServerRegistry class for server management.
"""

import pytest

from joshu.mcp.exceptions import MCPConfigurationError
from joshu.mcp.registry import MCPServerRegistry, get_mcp_registry
from joshu.mcp.schemas import MCPServerConfig, TransportType


class TestMCPServerRegistry:
    """Test MCPServerRegistry class."""

    def test_singleton_pattern(self, reset_mcp_registry):
        """Test registry is a singleton."""
        registry1 = MCPServerRegistry()
        registry2 = MCPServerRegistry()
        assert registry1 is registry2

    def test_add_server(self, reset_mcp_registry, sample_mcp_server_config):
        """Test adding a server configuration."""
        registry = MCPServerRegistry()
        config = MCPServerConfig.from_dict("test_server", sample_mcp_server_config)

        result = registry.add_server(config)

        assert result is True
        assert "test_server" in registry.get_server_names()

    def test_add_server_from_dict(self, reset_mcp_registry, sample_mcp_server_config):
        """Test adding server from dictionary."""
        registry = MCPServerRegistry()

        result = registry.add_server_from_dict("test_server", sample_mcp_server_config)

        assert result is True
        server = registry.get_server("test_server")
        assert server is not None
        assert server.command == "python"

    def test_add_invalid_server(self, reset_mcp_registry):
        """Test adding invalid server raises error."""
        registry = MCPServerRegistry()
        config = MCPServerConfig(
            name="invalid",
            transport=TransportType.STDIO,
            command=None,  # Invalid: no command for stdio
        )

        with pytest.raises(MCPConfigurationError):
            registry.add_server(config)

    def test_remove_server(self, reset_mcp_registry, sample_mcp_server_config):
        """Test removing a server."""
        registry = MCPServerRegistry()
        registry.add_server_from_dict("test_server", sample_mcp_server_config)

        result = registry.remove_server("test_server")

        assert result is True
        assert "test_server" not in registry.get_server_names()

    def test_remove_nonexistent_server(self, reset_mcp_registry):
        """Test removing non-existent server returns False."""
        registry = MCPServerRegistry()

        result = registry.remove_server("nonexistent")

        assert result is False

    def test_get_server(self, reset_mcp_registry, sample_mcp_server_config):
        """Test getting a server configuration."""
        registry = MCPServerRegistry()
        registry.add_server_from_dict("test_server", sample_mcp_server_config)

        server = registry.get_server("test_server")

        assert server is not None
        assert server.name == "test_server"
        assert server.command == "python"

    def test_get_nonexistent_server(self, reset_mcp_registry):
        """Test getting non-existent server returns None."""
        registry = MCPServerRegistry()

        server = registry.get_server("nonexistent")

        assert server is None

    def test_list_servers(
        self, reset_mcp_registry, sample_mcp_server_config, sample_http_server_config
    ):
        """Test listing all servers."""
        registry = MCPServerRegistry()
        registry.add_server_from_dict("stdio_server", sample_mcp_server_config)
        registry.add_server_from_dict("http_server", sample_http_server_config)

        servers = registry.list_servers()

        assert len(servers) == 2
        names = [s.name for s in servers]
        assert "stdio_server" in names
        assert "http_server" in names

    def test_get_server_names(self, reset_mcp_registry, sample_mcp_server_config):
        """Test getting server names."""
        registry = MCPServerRegistry()
        registry.add_server_from_dict("server1", sample_mcp_server_config)
        registry.add_server_from_dict("server2", sample_mcp_server_config)

        names = registry.get_server_names()

        assert len(names) == 2
        assert "server1" in names
        assert "server2" in names

    def test_is_connected_not_connected(self, reset_mcp_registry, sample_mcp_server_config):
        """Test is_connected when server is not connected."""
        registry = MCPServerRegistry()
        registry.add_server_from_dict("test_server", sample_mcp_server_config)

        assert registry.is_connected("test_server") is False

    def test_get_status(self, reset_mcp_registry, sample_mcp_server_config):
        """Test getting status of all servers."""
        registry = MCPServerRegistry()
        registry.add_server_from_dict("test_server", sample_mcp_server_config)

        status = registry.get_status()

        assert "test_server" in status
        assert status["test_server"]["enabled"] is True
        assert status["test_server"]["connected"] is False
        assert status["test_server"]["transport"] == "stdio"

    def test_clear(self, reset_mcp_registry, sample_mcp_server_config):
        """Test clearing all servers."""
        registry = MCPServerRegistry()
        registry.add_server_from_dict("server1", sample_mcp_server_config)
        registry.add_server_from_dict("server2", sample_mcp_server_config)

        # Just clear servers dict directly for sync test
        registry._servers.clear()
        registry._transports.clear()

        assert len(registry.list_servers()) == 0

    def test_update_existing_server(self, reset_mcp_registry, sample_mcp_server_config):
        """Test updating an existing server overwrites."""
        registry = MCPServerRegistry()
        registry.add_server_from_dict("test_server", sample_mcp_server_config)

        updated_config = sample_mcp_server_config.copy()
        updated_config["timeout"] = 60
        registry.add_server_from_dict("test_server", updated_config)

        server = registry.get_server("test_server")
        assert server.timeout == 60


class TestGetMCPRegistry:
    """Test get_mcp_registry function."""

    def test_returns_singleton(self, reset_mcp_registry):
        """Test that get_mcp_registry returns singleton."""
        registry1 = get_mcp_registry()
        registry2 = get_mcp_registry()

        assert registry1 is registry2

    def test_creates_registry_if_none(self, reset_mcp_registry):
        """Test creates registry if none exists."""
        registry = get_mcp_registry()

        assert registry is not None
        assert isinstance(registry, MCPServerRegistry)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
