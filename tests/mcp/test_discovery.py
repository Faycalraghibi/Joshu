"""
Unit tests for MCP Discovery.

Tests DiscoveredMCPTool and discover_mcp_tools function.
"""

from unittest.mock import AsyncMock, patch

import pytest

from joshu.mcp.discovery import (
    DiscoveredMCPTool,
    discover_mcp_tools,
    register_mcp_tools_with_joshu,
)
from joshu.mcp.registry import MCPServerRegistry
from joshu.mcp.schemas import MCPToolDefinition


class TestDiscoveredMCPTool:
    """Test DiscoveredMCPTool wrapper class."""

    def test_create_discovered_tool(self, sample_tool_definition, reset_mcp_registry):
        """Test creating a discovered MCP tool."""
        definition = MCPToolDefinition.from_mcp_response(sample_tool_definition, "test_server")
        registry = MCPServerRegistry()

        tool = DiscoveredMCPTool(definition, registry)

        assert tool.name == "test_tool"
        assert tool.server_name == "test_server"

    def test_sanitized_name(self, sample_tool_definition, reset_mcp_registry):
        """Test tool name sanitization."""
        definition = MCPToolDefinition(
            name="tool-with-dashes",
            description="Test",
            server_name="server",
        )
        registry = MCPServerRegistry()

        tool = DiscoveredMCPTool(definition, registry)

        # Should be sanitized to use underscores
        assert "-" not in tool.sanitized_name
        assert "server_" in tool.sanitized_name

    def test_description_sanitization(self, reset_mcp_registry):
        """Test description is sanitized."""
        definition = MCPToolDefinition(
            name="test_tool",
            description="A\x00valid\x1fdescription",  # With control chars
            server_name="server",
        )
        registry = MCPServerRegistry()

        tool = DiscoveredMCPTool(definition, registry)

        assert "\x00" not in tool.description
        assert "\x1f" not in tool.description

    def test_parameters_sanitization(self, reset_mcp_registry):
        """Test parameters are sanitized."""
        definition = MCPToolDefinition(
            name="test_tool",
            description="Test",
            parameters={
                "type": "object",
                "properties": {"arg": {"type": "string"}},
                "custom_key": "should_be_removed",
            },
            server_name="server",
        )
        registry = MCPServerRegistry()

        tool = DiscoveredMCPTool(definition, registry)

        assert "custom_key" not in tool.parameters

    def test_to_tool_spec_dict(self, sample_tool_definition, reset_mcp_registry):
        """Test conversion to ToolSpec dictionary."""
        definition = MCPToolDefinition.from_mcp_response(sample_tool_definition, "test_server")
        registry = MCPServerRegistry()

        tool = DiscoveredMCPTool(definition, registry)
        spec_dict = tool.to_tool_spec_dict()

        assert "name" in spec_dict
        assert "description" in spec_dict
        assert "parameters" in spec_dict
        assert "function" in spec_dict
        assert spec_dict["source"] == "mcp"
        assert spec_dict["server_name"] == "test_server"


class TestDiscoverMCPTools:
    """Test discover_mcp_tools function."""

    def test_discover_from_connected_server(
        self, sample_tool_definition, reset_mcp_registry, sample_mcp_server_config
    ):
        """Test discovering tools from a connected server."""
        import asyncio

        registry = MCPServerRegistry()
        registry.add_server_from_dict("test_server", sample_mcp_server_config)

        # Mock the transport
        mock_transport = AsyncMock()
        mock_transport.is_connected = True
        mock_transport.list_tools.return_value = [
            MCPToolDefinition.from_mcp_response(sample_tool_definition, "test_server")
        ]

        with patch.object(registry, "get_transport", return_value=mock_transport):
            with patch.object(registry, "is_connected", return_value=True):
                tools = asyncio.run(discover_mcp_tools(registry, connect_if_needed=False))

        assert len(tools) == 1
        assert tools[0].name == "test_tool"

    def test_discover_filters_excluded_tools(self, sample_tool_definition, reset_mcp_registry):
        """Test that excluded tools are filtered out."""
        import asyncio

        config = {
            "transport": "stdio",
            "command": "python",
            "exclude_tools": ["test_tool"],
            "enabled": True,
        }
        registry = MCPServerRegistry()
        registry.add_server_from_dict("test_server", config)

        mock_transport = AsyncMock()
        mock_transport.is_connected = True
        mock_transport.list_tools.return_value = [
            MCPToolDefinition.from_mcp_response(sample_tool_definition, "test_server")
        ]

        with patch.object(registry, "get_transport", return_value=mock_transport):
            with patch.object(registry, "is_connected", return_value=True):
                tools = asyncio.run(discover_mcp_tools(registry, connect_if_needed=False))

        # test_tool should be filtered out
        assert len(tools) == 0

    def test_discover_skips_disabled_servers(self, reset_mcp_registry):
        """Test that disabled servers are skipped."""
        import asyncio

        config = {
            "transport": "stdio",
            "command": "python",
            "enabled": False,
        }
        registry = MCPServerRegistry()
        registry.add_server_from_dict("disabled_server", config)

        tools = asyncio.run(discover_mcp_tools(registry, connect_if_needed=False))

        assert len(tools) == 0

    def test_discover_handles_connection_error(self, reset_mcp_registry, sample_mcp_server_config):
        """Test handling of connection errors during discovery."""
        import asyncio

        registry = MCPServerRegistry()
        registry.add_server_from_dict("test_server", sample_mcp_server_config)

        with patch.object(registry, "connect_server", side_effect=Exception("Connection failed")):
            with patch.object(registry, "is_connected", return_value=False):
                tools = asyncio.run(discover_mcp_tools(registry, connect_if_needed=True))

        # Should handle error gracefully
        assert len(tools) == 0


class TestRegisterMCPToolsWithJoshu:
    """Test register_mcp_tools_with_joshu function."""

    def test_register_tools(self, sample_tool_definition, reset_mcp_registry):
        """Test registering MCP tools with Joshu."""
        import asyncio

        from joshu.core.tool_registry import ToolRegistry

        # Clear tool registry
        tool_registry = ToolRegistry()
        tool_registry.clear()

        registry = MCPServerRegistry()

        # Create mock discovered tool
        definition = MCPToolDefinition.from_mcp_response(sample_tool_definition, "test_server")
        mock_tool = DiscoveredMCPTool(definition, registry)

        with patch("joshu.mcp.discovery.discover_mcp_tools", return_value=[mock_tool]):
            count = asyncio.run(register_mcp_tools_with_joshu(registry=registry))

        assert count == 1

        # Clean up
        tool_registry.clear()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
