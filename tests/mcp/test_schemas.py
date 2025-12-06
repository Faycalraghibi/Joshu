"""
Unit tests for MCP Schemas.

Tests MCPServerConfig, MCPToolDefinition, MCPResourceDefinition,
MCPPromptDefinition, and MCPToolResult classes.
"""

import pytest

from joshu.mcp.schemas import (
    MCPContentBlock,
    MCPPromptDefinition,
    MCPResourceDefinition,
    MCPServerConfig,
    MCPToolDefinition,
    MCPToolResult,
    TransportType,
)


class TestMCPServerConfig:
    """Test MCPServerConfig class."""

    def test_create_stdio_config(self, sample_mcp_server_config):
        """Test creating a stdio server config."""
        config = MCPServerConfig.from_dict("test_server", sample_mcp_server_config)

        assert config.name == "test_server"
        assert config.transport == TransportType.STDIO
        assert config.command == "python"
        assert config.args == ["-m", "test_server"]
        assert config.enabled is True
        assert config.timeout == 30

    def test_create_http_config(self, sample_http_server_config):
        """Test creating an HTTP server config."""
        config = MCPServerConfig.from_dict("http_server", sample_http_server_config)

        assert config.name == "http_server"
        assert config.transport == TransportType.HTTP
        assert config.url == "http://localhost:8080/mcp"
        assert config.enabled is True

    def test_validate_stdio_config(self):
        """Test validation of stdio config."""
        valid_config = MCPServerConfig(
            name="test",
            transport=TransportType.STDIO,
            command="python",
        )
        assert valid_config.validate() is True

        invalid_config = MCPServerConfig(
            name="test",
            transport=TransportType.STDIO,
            command=None,
        )
        assert invalid_config.validate() is False

    def test_validate_http_config(self):
        """Test validation of HTTP config."""
        valid_config = MCPServerConfig(
            name="test",
            transport=TransportType.HTTP,
            url="http://localhost:8080",
        )
        assert valid_config.validate() is True

        invalid_config = MCPServerConfig(
            name="test",
            transport=TransportType.HTTP,
            url=None,
        )
        assert invalid_config.validate() is False

    def test_to_dict(self):
        """Test conversion to dictionary."""
        config = MCPServerConfig(
            name="test",
            transport=TransportType.STDIO,
            command="python",
            args=["-m", "server"],
            enabled=True,
        )
        result = config.to_dict()

        assert result["transport"] == "stdio"
        assert result["command"] == "python"
        assert result["args"] == ["-m", "server"]
        assert result["enabled"] is True

    def test_include_exclude_tools(self):
        """Test include/exclude tools configuration."""
        config_dict = {
            "transport": "stdio",
            "command": "python",
            "include_tools": ["tool1", "tool2"],
            "exclude_tools": ["tool3"],
        }
        config = MCPServerConfig.from_dict("test", config_dict)

        assert config.include_tools == ["tool1", "tool2"]
        assert config.exclude_tools == ["tool3"]


class TestMCPToolDefinition:
    """Test MCPToolDefinition class."""

    def test_create_from_mcp_response(self, sample_tool_definition):
        """Test creating tool definition from MCP response."""
        tool = MCPToolDefinition.from_mcp_response(sample_tool_definition, "test_server")

        assert tool.name == "test_tool"
        assert tool.description == "A test tool for unit tests"
        assert tool.server_name == "test_server"
        assert "properties" in tool.parameters
        assert "query" in tool.parameters["properties"]

    def test_to_openai_format(self, sample_tool_definition):
        """Test conversion to OpenAI format."""
        tool = MCPToolDefinition.from_mcp_response(sample_tool_definition, "test_server")
        openai_format = tool.to_openai_format()

        assert openai_format["type"] == "function"
        assert openai_format["function"]["name"] == "test_tool"
        assert "parameters" in openai_format["function"]

    def test_empty_tool_definition(self):
        """Test creating tool with minimal data."""
        tool = MCPToolDefinition.from_mcp_response({}, "server")

        assert tool.name == ""
        assert tool.description == ""
        assert tool.server_name == "server"


class TestMCPResourceDefinition:
    """Test MCPResourceDefinition class."""

    def test_create_from_mcp_response(self, sample_resource_definition):
        """Test creating resource definition from MCP response."""
        resource = MCPResourceDefinition.from_mcp_response(
            sample_resource_definition, "test_server"
        )

        assert resource.uri == "file://test/resource"
        assert resource.name == "test_resource"
        assert resource.description == "A test resource"
        assert resource.mime_type == "text/plain"
        assert resource.server_name == "test_server"


class TestMCPPromptDefinition:
    """Test MCPPromptDefinition class."""

    def test_create_from_mcp_response(self, sample_prompt_definition):
        """Test creating prompt definition from MCP response."""
        prompt = MCPPromptDefinition.from_mcp_response(sample_prompt_definition, "test_server")

        assert prompt.name == "test_prompt"
        assert prompt.description == "A test prompt template"
        assert len(prompt.arguments) == 1
        assert prompt.arguments[0]["name"] == "topic"


class TestMCPToolResult:
    """Test MCPToolResult class."""

    def test_successful_result(self):
        """Test successful tool result."""
        result = MCPToolResult(
            success=True,
            content="Result content",
            tool_name="test_tool",
            server_name="test_server",
        )

        result_dict = result.to_dict()
        assert result_dict["success"] is True
        assert result_dict["result"] == "Result content"
        assert result_dict["tool_name"] == "test_tool"
        assert result_dict["server_name"] == "test_server"

    def test_failed_result(self):
        """Test failed tool result."""
        result = MCPToolResult(
            success=False,
            error="Something went wrong",
            tool_name="test_tool",
            server_name="test_server",
            is_error=True,
        )

        result_dict = result.to_dict()
        assert result_dict["success"] is False
        assert result_dict["error"] == "Something went wrong"


class TestMCPContentBlock:
    """Test MCPContentBlock class."""

    def test_text_content_block(self):
        """Test text content block."""
        block = MCPContentBlock.from_mcp_response(
            {
                "type": "text",
                "text": "Hello, world!",
            }
        )

        assert block.type == "text"
        assert block.text == "Hello, world!"
        assert block.get_text_content() == "Hello, world!"

    def test_image_content_block(self):
        """Test image content block."""
        block = MCPContentBlock.from_mcp_response(
            {
                "type": "image",
                "data": "base64data",
                "mimeType": "image/png",
            }
        )

        assert block.type == "image"
        assert block.get_text_content() == "[Image content]"

    def test_resource_content_block(self):
        """Test resource content block."""
        block = MCPContentBlock.from_mcp_response(
            {
                "type": "resource",
                "uri": "file://test",
            }
        )

        assert block.type == "resource"
        assert block.get_text_content() == "[Resource: file://test]"


class TestTransportType:
    """Test TransportType enum."""

    def test_transport_values(self):
        """Test transport type values."""
        assert TransportType.STDIO.value == "stdio"
        assert TransportType.HTTP.value == "http"
        assert TransportType.SSE.value == "sse"

    def test_transport_from_string(self):
        """Test creating transport type from string."""
        assert TransportType("stdio") == TransportType.STDIO
        assert TransportType("http") == TransportType.HTTP


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
