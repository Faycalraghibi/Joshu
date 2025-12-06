"""
MCP Test Configuration and Fixtures.
"""

from typing import Any, Dict
from unittest.mock import AsyncMock

import pytest


@pytest.fixture
def sample_mcp_server_config() -> Dict[str, Any]:
    """Sample MCP server configuration."""
    return {
        "transport": "stdio",
        "command": "python",
        "args": ["-m", "test_server"],
        "enabled": True,
        "timeout": 30,
    }


@pytest.fixture
def sample_http_server_config() -> Dict[str, Any]:
    """Sample HTTP MCP server configuration."""
    return {
        "transport": "http",
        "url": "http://localhost:8080/mcp",
        "enabled": True,
        "timeout": 30,
    }


@pytest.fixture
def sample_tool_definition() -> Dict[str, Any]:
    """Sample MCP tool definition from server response."""
    return {
        "name": "test_tool",
        "description": "A test tool for unit tests",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "The query parameter"},
                "count": {"type": "integer", "default": 5},
            },
            "required": ["query"],
        },
    }


@pytest.fixture
def sample_resource_definition() -> Dict[str, Any]:
    """Sample MCP resource definition."""
    return {
        "uri": "file://test/resource",
        "name": "test_resource",
        "description": "A test resource",
        "mimeType": "text/plain",
    }


@pytest.fixture
def sample_prompt_definition() -> Dict[str, Any]:
    """Sample MCP prompt definition."""
    return {
        "name": "test_prompt",
        "description": "A test prompt template",
        "arguments": [
            {"name": "topic", "description": "The topic to discuss", "required": True},
        ],
    }


@pytest.fixture
def mock_transport():
    """Create a mock MCP transport."""
    transport = AsyncMock()
    transport.is_connected = True
    transport.server_name = "test_server"
    transport.connect.return_value = True
    transport.disconnect.return_value = None
    transport.list_tools.return_value = []
    transport.list_resources.return_value = []
    transport.list_prompts.return_value = []
    return transport


@pytest.fixture
def reset_mcp_registry():
    """Reset MCP registry singleton for test isolation."""
    from joshu.mcp.registry import MCPServerRegistry

    # Clear existing instance
    MCPServerRegistry._instance = None
    yield
    # Clean up after test
    MCPServerRegistry._instance = None
