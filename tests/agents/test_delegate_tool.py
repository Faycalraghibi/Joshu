"""
Unit tests for DelegateToAgentTool.

Run with: pytest tests/agents/test_delegate_tool.py -v
"""

import pytest

from joshu.agents.definitions import (
    AgentDefinition,
    AgentModelConfig,
    FieldDefinition,
    InputConfig,
    PromptConfig,
)
from joshu.agents.delegate_tool import (
    DelegateToAgentTool,
    DelegationRequest,
    create_delegate_tool,
)
from joshu.agents.exceptions import AgentNotFoundError, AgentValidationError
from joshu.agents.registry import AgentRegistry


class TestDelegationRequest:
    """Test DelegationRequest data structure."""

    def test_create_request(self):
        """Test creating a delegation request."""
        agent = AgentDefinition(
            name="test_agent",
            description="Test",
            prompt_config=PromptConfig(system_prompt="Test"),
            model_config=AgentModelConfig(model_name="gpt-4o"),
        )
        request = DelegationRequest(
            agent_name="test_agent",
            agent=agent,
            inputs={"query": "test"},
            task_description="Do something",
        )
        assert request.agent_name == "test_agent"
        assert request.inputs == {"query": "test"}

    def test_to_dict(self):
        """Test serialization to dictionary."""
        agent = AgentDefinition(
            name="test_agent",
            description="Test",
            prompt_config=PromptConfig(system_prompt="Test"),
            model_config=AgentModelConfig(model_name="gpt-4o"),
        )
        request = DelegationRequest(
            agent_name="test_agent",
            agent=agent,
            inputs={"x": 1},
            task_description="Task",
        )
        data = request.to_dict()
        assert data["agent_name"] == "test_agent"
        assert data["inputs"] == {"x": 1}
        assert data["task_description"] == "Task"


class TestDelegateToAgentTool:
    """Test DelegateToAgentTool functionality."""

    def setup_method(self):
        """Clear registry before each test."""
        registry = AgentRegistry()
        registry.clear()

    def teardown_method(self):
        """Clear registry after each test."""
        registry = AgentRegistry()
        registry.clear()

    @pytest.fixture
    def sample_agent(self):
        """Create a sample agent."""
        agent = AgentDefinition(
            name="search_agent",
            description="Searches for information",
            prompt_config=PromptConfig(system_prompt="You are a search agent."),
            model_config=AgentModelConfig(model_name="gpt-4o"),
            input_config=InputConfig(
                fields=[
                    FieldDefinition(name="query", field_type="string", required=True),
                    FieldDefinition(name="limit", field_type="integer", required=False),
                ]
            ),
        )
        return agent

    def test_tool_name(self):
        """Test tool name is correct."""
        tool = DelegateToAgentTool()
        assert tool.name == "delegate_to_agent"

    def test_description_with_no_agents(self):
        """Test description when no agents registered."""
        tool = DelegateToAgentTool()
        desc = tool.description
        assert "No agents currently available" in desc

    def test_description_with_agents(self, sample_agent):
        """Test description includes registered agents."""
        registry = AgentRegistry()
        registry.register(sample_agent)

        tool = DelegateToAgentTool(registry)
        desc = tool.description
        assert "search_agent" in desc
        assert "Searches for information" in desc

    def test_build_dynamic_schema_empty(self):
        """Test schema with no agents."""
        tool = DelegateToAgentTool()
        schema = tool.build_dynamic_schema()

        assert schema["type"] == "object"
        assert "agent_name" in schema["properties"]
        assert "no_agents_available" in schema["properties"]["agent_name"]["enum"]

    def test_build_dynamic_schema_with_agents(self, sample_agent):
        """Test schema includes registered agents."""
        registry = AgentRegistry()
        registry.register(sample_agent)

        tool = DelegateToAgentTool(registry)
        schema = tool.build_dynamic_schema()

        assert "agent_name" in schema["properties"]
        assert "search_agent" in schema["properties"]["agent_name"]["enum"]

    def test_validate_delegation_success(self, sample_agent):
        """Test successful delegation validation."""
        registry = AgentRegistry()
        registry.register(sample_agent)

        tool = DelegateToAgentTool(registry)
        request = tool.validate_delegation(
            agent_name="search_agent",
            inputs={"query": "AI research"},
            task_description="Find papers",
        )

        assert isinstance(request, DelegationRequest)
        assert request.agent_name == "search_agent"
        assert request.inputs["query"] == "AI research"
        assert request.task_description == "Find papers"
        assert request.agent is sample_agent

    def test_validate_delegation_agent_not_found(self):
        """Test validation fails for non-existent agent."""
        tool = DelegateToAgentTool()

        with pytest.raises(AgentNotFoundError) as exc_info:
            tool.validate_delegation("nonexistent_agent")

        assert "nonexistent_agent" in str(exc_info.value)

    def test_validate_delegation_disabled_agent(self, sample_agent):
        """Test validation fails for disabled agent."""
        registry = AgentRegistry()
        disabled_agent = AgentDefinition(
            name="disabled_agent",
            description="Disabled",
            prompt_config=PromptConfig(system_prompt="Test"),
            model_config=AgentModelConfig(model_name="gpt-4o"),
            enabled=False,
        )
        registry.register(disabled_agent)

        tool = DelegateToAgentTool(registry)

        with pytest.raises(AgentValidationError) as exc_info:
            tool.validate_delegation("disabled_agent")

        assert "disabled" in str(exc_info.value)

    def test_validate_delegation_missing_required_input(self, sample_agent):
        """Test validation fails for missing required input."""
        registry = AgentRegistry()
        registry.register(sample_agent)

        tool = DelegateToAgentTool(registry)

        with pytest.raises(AgentValidationError) as exc_info:
            tool.validate_delegation("search_agent", inputs={})

        assert "query" in str(exc_info.value)
        assert "required" in str(exc_info.value).lower()

    def test_validate_delegation_wrong_input_type(self, sample_agent):
        """Test validation fails for wrong input type."""
        registry = AgentRegistry()
        registry.register(sample_agent)

        tool = DelegateToAgentTool(registry)

        with pytest.raises(AgentValidationError) as exc_info:
            tool.validate_delegation(
                "search_agent",
                inputs={"query": 123},  # Should be string
            )

        assert "string" in str(exc_info.value)

    def test_validate_delegation_optional_input(self, sample_agent):
        """Test optional inputs are not required."""
        registry = AgentRegistry()
        registry.register(sample_agent)

        tool = DelegateToAgentTool(registry)
        request = tool.validate_delegation(
            "search_agent",
            inputs={"query": "test"},  # limit is optional
        )

        assert request.inputs == {"query": "test"}


class TestToolSpec:
    """Test ToolSpec generation."""

    def setup_method(self):
        registry = AgentRegistry()
        registry.clear()

    def teardown_method(self):
        registry = AgentRegistry()
        registry.clear()

    def test_to_tool_spec(self):
        """Test conversion to ToolSpec."""
        tool = DelegateToAgentTool()
        spec = tool.to_tool_spec()

        assert spec.name == "delegate_to_agent"
        assert spec.function is not None
        assert spec.enabled is True

    def test_tool_function_success(self):
        """Test tool function returns success for valid delegation."""
        registry = AgentRegistry()
        agent = AgentDefinition(
            name="helper_agent",
            description="Helps",
            prompt_config=PromptConfig(system_prompt="Test"),
            model_config=AgentModelConfig(model_name="gpt-4o"),
        )
        registry.register(agent)

        tool = DelegateToAgentTool(registry)
        result = tool._tool_function("helper_agent")

        assert result["success"] is True
        assert "delegation_request" in result
        assert result["delegation_request"]["agent_name"] == "helper_agent"

    def test_tool_function_failure(self):
        """Test tool function returns failure for invalid delegation."""
        tool = DelegateToAgentTool()
        result = tool._tool_function("nonexistent")

        assert result["success"] is False
        assert "error" in result


class TestCreateDelegateTool:
    """Test create_delegate_tool helper."""

    def setup_method(self):
        registry = AgentRegistry()
        registry.clear()

    def teardown_method(self):
        registry = AgentRegistry()
        registry.clear()

    def test_create_delegate_tool(self):
        """Test convenience function."""
        spec = create_delegate_tool()

        assert spec.name == "delegate_to_agent"
        assert spec.function is not None


class TestGetAgentsForPrompt:
    """Test prompt generation for agents."""

    def setup_method(self):
        registry = AgentRegistry()
        registry.clear()

    def teardown_method(self):
        registry = AgentRegistry()
        registry.clear()

    def test_no_agents(self):
        """Test prompt with no agents."""
        tool = DelegateToAgentTool()
        prompt = tool.get_agents_for_prompt()
        assert "No subagents available" in prompt

    def test_with_agents(self):
        """Test prompt includes agent details."""
        registry = AgentRegistry()
        agent = AgentDefinition(
            name="code_agent",
            description="Writes code",
            prompt_config=PromptConfig(system_prompt="Test"),
            model_config=AgentModelConfig(model_name="gpt-4o"),
        )
        registry.register(agent)

        tool = DelegateToAgentTool(registry)
        prompt = tool.get_agents_for_prompt()

        assert "delegate" in prompt.lower()
        assert "code_agent" in prompt


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
