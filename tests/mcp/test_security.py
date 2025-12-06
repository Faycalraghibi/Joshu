"""
Unit tests for MCP Security utilities.

Tests sanitization, validation, and conflict resolution.
"""

import pytest

from joshu.mcp.exceptions import MCPSecurityError
from joshu.mcp.schemas import MCPToolDefinition
from joshu.mcp.security import (
    is_tool_allowed,
    resolve_conflict,
    sanitize_description,
    sanitize_schema,
    sanitize_tool_name,
    validate_tool_definition,
)


class TestSanitizeToolName:
    """Test tool name sanitization."""

    def test_valid_name_unchanged(self):
        """Test that valid names pass through unchanged."""
        assert sanitize_tool_name("valid_name") == "valid_name"
        assert sanitize_tool_name("validName") == "validName"

    def test_removes_invalid_characters(self):
        """Test removal of invalid characters."""
        assert sanitize_tool_name("tool-name") == "tool_name"
        assert sanitize_tool_name("tool.name") == "tool_name"
        assert sanitize_tool_name("tool@name!") == "tool_name_"

    def test_adds_prefix_if_starts_with_number(self):
        """Test prefix added for names starting with number."""
        result = sanitize_tool_name("123tool")
        assert result.startswith("tool_")

    def test_with_server_namespace(self):
        """Test namespacing with server name."""
        result = sanitize_tool_name("tool_name", "server")
        assert result == "server_tool_name"

    def test_length_truncation(self):
        """Test that long names are truncated."""
        long_name = "a" * 100
        result = sanitize_tool_name(long_name)
        assert len(result) <= 64

    def test_empty_name_raises_error(self):
        """Test that empty name raises error."""
        with pytest.raises(MCPSecurityError):
            sanitize_tool_name("")


class TestSanitizeDescription:
    """Test description sanitization."""

    def test_normal_description(self):
        """Test normal description passes through."""
        desc = "A normal description"
        assert sanitize_description(desc) == desc

    def test_removes_control_characters(self):
        """Test removal of control characters."""
        desc = "Hello\x00World\x1fTest"
        result = sanitize_description(desc)
        assert "\x00" not in result
        assert "\x1f" not in result

    def test_truncates_long_description(self):
        """Test truncation of long descriptions."""
        long_desc = "a" * 2000
        result = sanitize_description(long_desc)
        assert len(result) <= 1024
        assert result.endswith("...")

    def test_empty_description(self):
        """Test empty description returns empty string."""
        assert sanitize_description("") == ""
        assert sanitize_description(None) == ""


class TestSanitizeSchema:
    """Test schema sanitization."""

    def test_valid_schema_unchanged(self):
        """Test valid schema passes through with allowed keys."""
        schema = {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Name"},
            },
            "required": ["name"],
        }
        result = sanitize_schema(schema)
        assert result["type"] == "object"
        assert "properties" in result
        assert "required" in result

    def test_removes_unknown_keys(self):
        """Test removal of unknown keys."""
        schema = {
            "type": "object",
            "properties": {},
            "unknown_key": "value",
        }
        result = sanitize_schema(schema)
        assert "unknown_key" not in result

    def test_invalid_type_corrected(self):
        """Test invalid types are corrected to string."""
        schema = {
            "type": "invalid_type",
            "properties": {},
        }
        result = sanitize_schema(schema)
        assert result["type"] == "string"

    def test_max_depth_enforced(self):
        """Test maximum nesting depth is enforced."""
        # Create deeply nested schema
        deep_schema = {"type": "object", "properties": {}}
        current = deep_schema
        for i in range(10):
            current["properties"]["nested"] = {"type": "object", "properties": {}}
            current = current["properties"]["nested"]

        with pytest.raises(MCPSecurityError):
            sanitize_schema(deep_schema)

    def test_non_dict_returns_default(self):
        """Test non-dict input returns default schema."""
        result = sanitize_schema("not a dict")
        assert result == {"type": "object", "properties": {}}


class TestIsToolAllowed:
    """Test tool filtering."""

    def test_no_filters_allows_all(self):
        """Test that no filters allows all tools."""
        assert is_tool_allowed("any_tool", [], []) is True

    def test_exclude_list(self):
        """Test exclusion list works."""
        assert is_tool_allowed("bad_tool", [], ["bad_tool"]) is False
        assert is_tool_allowed("good_tool", [], ["bad_tool"]) is True

    def test_include_list(self):
        """Test inclusion list works."""
        assert is_tool_allowed("good_tool", ["good_tool"], []) is True
        assert is_tool_allowed("other_tool", ["good_tool"], []) is False

    def test_exclude_overrides_include(self):
        """Test that exclude takes precedence."""
        assert is_tool_allowed("tool", ["tool"], ["tool"]) is False


class TestResolveConflict:
    """Test conflict resolution."""

    def test_no_conflict(self):
        """Test when there's no conflict."""
        tool = MCPToolDefinition(
            name="new_tool",
            description="A new tool",
            server_name="server",
        )
        result = resolve_conflict(tool, {"existing_tool"})
        assert result == "new_tool"

    def test_namespace_resolution(self):
        """Test namespace conflict resolution."""
        tool = MCPToolDefinition(
            name="existing_tool",
            description="A tool",
            server_name="myserver",
        )
        result = resolve_conflict(tool, {"existing_tool"}, strategy="namespace")
        assert "myserver" in result
        assert result != "existing_tool"

    def test_skip_raises_error(self):
        """Test skip strategy raises error on conflict."""
        tool = MCPToolDefinition(
            name="existing_tool",
            description="A tool",
            server_name="server",
        )
        with pytest.raises(MCPSecurityError):
            resolve_conflict(tool, {"existing_tool"}, strategy="skip")

    def test_reserved_name_cannot_replace(self):
        """Test reserved names cannot be replaced."""
        tool = MCPToolDefinition(
            name="web_search",  # Reserved
            description="A tool",
            server_name="server",
        )
        with pytest.raises(MCPSecurityError):
            resolve_conflict(tool, {"web_search"}, strategy="replace")


class TestValidateToolDefinition:
    """Test tool definition validation."""

    def test_valid_tool(self):
        """Test valid tool passes validation."""
        tool = MCPToolDefinition(
            name="valid_tool",
            description="A valid tool",
            parameters={"type": "object", "properties": {}},
        )
        assert validate_tool_definition(tool) is True

    def test_missing_name(self):
        """Test missing name fails validation."""
        tool = MCPToolDefinition(
            name="",
            description="No name",
        )
        assert validate_tool_definition(tool) is False

    def test_invalid_name_format(self):
        """Test invalid name format fails validation."""
        tool = MCPToolDefinition(
            name="123-invalid",  # Starts with number
            description="Invalid name",
        )
        assert validate_tool_definition(tool) is False

    def test_invalid_parameters(self):
        """Test invalid parameters type fails validation."""
        tool = MCPToolDefinition(
            name="valid_name",
            description="Valid",
            parameters={"type": "array"},  # Should be object
        )
        assert validate_tool_definition(tool) is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
