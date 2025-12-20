"""
Unit tests for Agent Definition dataclasses.

Run with: pytest tests/agents/test_agent_definitions.py -v
"""

import pytest

from joshu.agents.definitions import (
    AgentDefinition,
    AgentModelConfig,
    FieldDefinition,
    InputConfig,
    PromptConfig,
    RunConfig,
    ToolConfig,
)


class TestFieldDefinition:
    """Test FieldDefinition validation."""

    def test_valid_string_field(self):
        """Test valid string field."""
        field = FieldDefinition(name="query", field_type="string", description="Search query")
        assert field.validate()

    def test_valid_integer_field(self):
        """Test valid integer field."""
        field = FieldDefinition(name="count", field_type="integer", required=False, default=10)
        assert field.validate()

    def test_all_valid_types(self):
        """Test all valid field types."""
        for field_type in ["string", "integer", "number", "boolean", "array", "object"]:
            field = FieldDefinition(name="test", field_type=field_type)
            assert field.validate(), f"Failed for type: {field_type}"

    def test_invalid_field_type(self):
        """Test invalid field type fails validation."""
        field = FieldDefinition(name="test", field_type="invalid_type")
        assert not field.validate()

    def test_invalid_field_name_empty(self):
        """Test empty field name fails validation."""
        field = FieldDefinition(name="", field_type="string")
        assert not field.validate()

    def test_invalid_field_name_starts_with_number(self):
        """Test field name starting with number fails validation."""
        field = FieldDefinition(name="123field", field_type="string")
        assert not field.validate()

    def test_valid_field_name_with_underscore(self):
        """Test field name with underscores is valid."""
        field = FieldDefinition(name="my_field_name", field_type="string")
        assert field.validate()

    def test_array_with_valid_items_type(self):
        """Test array field with valid items type."""
        field = FieldDefinition(name="items", field_type="array", items_type="string")
        assert field.validate()

    def test_array_with_invalid_items_type(self):
        """Test array field with invalid items type fails."""
        field = FieldDefinition(name="items", field_type="array", items_type="invalid")
        assert not field.validate()

    def test_nested_object_validation(self):
        """Test nested object properties are validated."""
        nested = FieldDefinition(name="bad", field_type="invalid")
        field = FieldDefinition(
            name="parent",
            field_type="object",
            properties=[nested],
        )
        assert not field.validate()

    def test_valid_nested_object(self):
        """Test valid nested object passes validation."""
        nested = FieldDefinition(name="child", field_type="string")
        field = FieldDefinition(
            name="parent",
            field_type="object",
            properties=[nested],
        )
        assert field.validate()


class TestInputConfig:
    """Test InputConfig validation."""

    def test_empty_fields(self):
        """Test InputConfig with no fields is valid."""
        config = InputConfig(fields=[])
        assert config.validate()

    def test_valid_fields(self):
        """Test InputConfig with valid fields."""
        config = InputConfig(
            fields=[
                FieldDefinition(name="query", field_type="string"),
                FieldDefinition(name="limit", field_type="integer", required=False),
            ]
        )
        assert config.validate()

    def test_invalid_field_fails(self):
        """Test InputConfig with invalid field fails."""
        config = InputConfig(
            fields=[
                FieldDefinition(name="bad", field_type="invalid"),
            ]
        )
        assert not config.validate()


class TestPromptConfig:
    """Test PromptConfig validation."""

    def test_valid_prompt(self):
        """Test valid prompt config."""
        config = PromptConfig(system_prompt="You are a helpful assistant.")
        assert config.validate()

    def test_empty_system_prompt(self):
        """Test empty system prompt fails."""
        config = PromptConfig(system_prompt="")
        assert not config.validate()

    def test_whitespace_only_system_prompt(self):
        """Test whitespace-only system prompt fails."""
        config = PromptConfig(system_prompt="   ")
        assert not config.validate()

    def test_with_user_prompt_template(self):
        """Test config with user prompt template."""
        config = PromptConfig(
            system_prompt="You are a helpful assistant.",
            user_prompt_template="User query: {query}",
        )
        assert config.validate()


class TestAgentModelConfig:
    """Test AgentModelConfig validation."""

    def test_valid_model_config(self):
        """Test valid model config."""
        config = AgentModelConfig(model_name="gpt-4o")
        assert config.validate()

    def test_empty_model_name(self):
        """Test empty model name fails."""
        config = AgentModelConfig(model_name="")
        assert not config.validate()

    def test_with_fallbacks(self):
        """Test model config with fallbacks."""
        config = AgentModelConfig(
            model_name="gpt-4o",
            fallback_models=["gpt-4o-mini", "claude-3-sonnet"],
        )
        assert config.validate()


class TestRunConfig:
    """Test RunConfig validation."""

    def test_default_values(self):
        """Test RunConfig with default values is valid."""
        config = RunConfig()
        assert config.validate()

    def test_custom_values(self):
        """Test RunConfig with custom values."""
        config = RunConfig(max_turns=5, max_execution_time=60, retry_limit=1)
        assert config.validate()

    def test_zero_max_turns_fails(self):
        """Test zero max_turns fails."""
        config = RunConfig(max_turns=0)
        assert not config.validate()

    def test_negative_max_turns_fails(self):
        """Test negative max_turns fails."""
        config = RunConfig(max_turns=-1)
        assert not config.validate()

    def test_negative_max_execution_time_fails(self):
        """Test negative max_execution_time fails."""
        config = RunConfig(max_execution_time=-1)
        assert not config.validate()

    def test_negative_retry_limit_fails(self):
        """Test negative retry_limit fails."""
        config = RunConfig(retry_limit=-1)
        assert not config.validate()

    def test_zero_retry_limit_valid(self):
        """Test zero retry_limit is valid (no retries allowed)."""
        config = RunConfig(retry_limit=0)
        assert config.validate()


class TestToolConfig:
    """Test ToolConfig validation."""

    def test_empty_allowed_tools(self):
        """Test empty allowed_tools is valid."""
        config = ToolConfig(allowed_tools=[])
        assert config.validate()

    def test_valid_allowed_tools(self):
        """Test valid allowed_tools list."""
        config = ToolConfig(allowed_tools=["web_search", "web_fetch"])
        assert config.validate()


class TestAgentDefinition:
    """Test AgentDefinition validation."""

    @pytest.fixture
    def valid_agent(self):
        """Create a valid agent definition for testing."""
        return AgentDefinition(
            name="test_agent",
            description="A test agent for unit testing",
            prompt_config=PromptConfig(system_prompt="You are a test assistant."),
            model_config=AgentModelConfig(model_name="gpt-4o"),
        )

    def test_valid_agent(self, valid_agent):
        """Test valid agent definition passes validation."""
        assert valid_agent.validate()

    def test_empty_name_fails(self):
        """Test empty agent name fails validation."""
        agent = AgentDefinition(
            name="",
            description="A test agent",
            prompt_config=PromptConfig(system_prompt="Test"),
            model_config=AgentModelConfig(model_name="gpt-4o"),
        )
        assert not agent.validate()

    def test_invalid_name_format_fails(self):
        """Test invalid agent name format fails."""
        agent = AgentDefinition(
            name="123-bad-name",
            description="A test agent",
            prompt_config=PromptConfig(system_prompt="Test"),
            model_config=AgentModelConfig(model_name="gpt-4o"),
        )
        assert not agent.validate()

    def test_empty_description_fails(self):
        """Test empty description fails validation."""
        agent = AgentDefinition(
            name="test_agent",
            description="",
            prompt_config=PromptConfig(system_prompt="Test"),
            model_config=AgentModelConfig(model_name="gpt-4o"),
        )
        assert not agent.validate()

    def test_invalid_version_format_fails(self):
        """Test invalid version format fails validation."""
        agent = AgentDefinition(
            name="test_agent",
            description="A test agent",
            prompt_config=PromptConfig(system_prompt="Test"),
            model_config=AgentModelConfig(model_name="gpt-4o"),
            version="1.0",  # Missing patch version
        )
        assert not agent.validate()

    def test_valid_version_format(self, valid_agent):
        """Test valid version formats."""
        for version in ["1.0.0", "0.1.0", "10.20.30"]:
            agent = AgentDefinition(
                name="test_agent",
                description="A test agent",
                prompt_config=PromptConfig(system_prompt="Test"),
                model_config=AgentModelConfig(model_name="gpt-4o"),
                version=version,
            )
            assert agent.validate(), f"Failed for version: {version}"

    def test_with_input_config(self, valid_agent):
        """Test agent with input config."""
        agent = AgentDefinition(
            name="test_agent",
            description="A test agent",
            prompt_config=PromptConfig(system_prompt="Test"),
            model_config=AgentModelConfig(model_name="gpt-4o"),
            input_config=InputConfig(
                fields=[
                    FieldDefinition(name="query", field_type="string"),
                ]
            ),
        )
        assert agent.validate()

    def test_invalid_input_config_fails(self):
        """Test agent with invalid input config fails."""
        agent = AgentDefinition(
            name="test_agent",
            description="A test agent",
            prompt_config=PromptConfig(system_prompt="Test"),
            model_config=AgentModelConfig(model_name="gpt-4o"),
            input_config=InputConfig(
                fields=[
                    FieldDefinition(name="bad", field_type="invalid"),
                ]
            ),
        )
        assert not agent.validate()

    def test_to_dict(self, valid_agent):
        """Test serialization to dictionary."""
        data = valid_agent.to_dict()
        assert data["name"] == "test_agent"
        assert data["description"] == "A test agent for unit testing"
        assert data["prompt_config"]["system_prompt"] == "You are a test assistant."
        assert data["model_config"]["model_name"] == "gpt-4o"
        assert data["enabled"] is True
        assert data["version"] == "1.0.0"

    def test_from_dict_roundtrip(self, valid_agent):
        """Test dict serialization and deserialization roundtrip."""
        data = valid_agent.to_dict()
        restored = AgentDefinition.from_dict(data)
        assert restored.name == valid_agent.name
        assert restored.description == valid_agent.description
        assert restored.prompt_config.system_prompt == valid_agent.prompt_config.system_prompt
        assert restored.model_config.model_name == valid_agent.model_config.model_name
        assert restored.validate()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
