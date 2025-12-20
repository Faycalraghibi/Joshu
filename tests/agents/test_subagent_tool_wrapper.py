"""
Unit tests for SubagentToolWrapper.

Run with: pytest tests/agents/test_subagent_tool_wrapper.py -v
"""

import pytest

from joshu.agents.definitions import (
    AgentDefinition,
    AgentModelConfig,
    FieldDefinition,
    InputConfig,
    PromptConfig,
)
from joshu.agents.exceptions import AgentValidationError
from joshu.agents.tool_wrapper import SubagentToolWrapper, create_subagent_tools


class TestSubagentToolWrapper:
    """Test SubagentToolWrapper functionality."""

    @pytest.fixture
    def simple_agent(self):
        """Create a simple agent without input config."""
        return AgentDefinition(
            name="simple_agent",
            description="A simple agent for testing",
            prompt_config=PromptConfig(system_prompt="You are a simple assistant."),
            model_config=AgentModelConfig(model_name="gpt-4o"),
        )

    @pytest.fixture
    def agent_with_inputs(self):
        """Create an agent with input configuration."""
        return AgentDefinition(
            name="search_agent",
            description="An agent that searches for information",
            prompt_config=PromptConfig(system_prompt="You are a search assistant."),
            model_config=AgentModelConfig(model_name="gpt-4o"),
            input_config=InputConfig(
                fields=[
                    FieldDefinition(
                        name="query",
                        field_type="string",
                        description="Search query",
                        required=True,
                    ),
                    FieldDefinition(
                        name="limit",
                        field_type="integer",
                        description="Max results",
                        required=False,
                        default=10,
                    ),
                ]
            ),
        )

    @pytest.fixture
    def mock_handler(self):
        """Create a mock invocation handler."""

        def handler(agent_name, **kwargs):
            return {
                "success": True,
                "result": f"Executed {agent_name} with {kwargs}",
            }

        return handler

    def test_create_wrapper(self, simple_agent, mock_handler):
        """Test creating a SubagentToolWrapper."""
        wrapper = SubagentToolWrapper(simple_agent, mock_handler)
        assert wrapper.agent.name == "simple_agent"

    def test_wrapper_invalid_agent_raises(self, mock_handler):
        """Test wrapper creation with invalid agent raises error."""
        invalid_agent = AgentDefinition(
            name="",  # Invalid
            description="Bad agent",
            prompt_config=PromptConfig(system_prompt="Test"),
            model_config=AgentModelConfig(model_name="gpt-4o"),
        )
        with pytest.raises(AgentValidationError):
            SubagentToolWrapper(invalid_agent, mock_handler)

    def test_name_property(self, simple_agent, mock_handler):
        """Test name property uses prefix."""
        wrapper = SubagentToolWrapper(simple_agent, mock_handler)
        assert wrapper.name == "agent_simple_agent"

    def test_custom_name_prefix(self, simple_agent, mock_handler):
        """Test custom name prefix."""
        wrapper = SubagentToolWrapper(simple_agent, mock_handler, tool_name_prefix="subagent_")
        assert wrapper.name == "subagent_simple_agent"

    def test_description_property(self, simple_agent, mock_handler):
        """Test description property from agent."""
        wrapper = SubagentToolWrapper(simple_agent, mock_handler)
        assert wrapper.description == "A simple agent for testing"

    def test_parameters_empty_for_no_input_config(self, simple_agent, mock_handler):
        """Test parameters is empty object when no input config."""
        wrapper = SubagentToolWrapper(simple_agent, mock_handler)
        params = wrapper.parameters
        assert params["type"] == "object"
        assert params["properties"] == {}

    def test_parameters_from_input_config(self, agent_with_inputs, mock_handler):
        """Test parameters generated from input config."""
        wrapper = SubagentToolWrapper(agent_with_inputs, mock_handler)
        params = wrapper.parameters

        assert params["type"] == "object"
        assert "query" in params["properties"]
        assert "limit" in params["properties"]
        assert params["properties"]["query"]["type"] == "string"
        assert params["properties"]["limit"]["type"] == "integer"
        assert "query" in params["required"]
        assert "limit" not in params["required"]


class TestToToolSpec:
    """Test to_tool_spec method."""

    @pytest.fixture
    def agent(self):
        """Create a test agent."""
        return AgentDefinition(
            name="tool_agent",
            description="An agent to wrap as tool",
            prompt_config=PromptConfig(system_prompt="You are a tool."),
            model_config=AgentModelConfig(model_name="gpt-4o"),
        )

    @pytest.fixture
    def mock_handler(self):
        def handler(agent_name, **kwargs):
            return {"result": "ok"}

        return handler

    def test_to_tool_spec(self, agent, mock_handler):
        """Test converting wrapper to ToolSpec."""
        wrapper = SubagentToolWrapper(agent, mock_handler)
        spec = wrapper.to_tool_spec()

        assert spec.name == "agent_tool_agent"
        assert spec.description == "An agent to wrap as tool"
        assert spec.parameters["type"] == "object"
        assert spec.function is wrapper

    def test_tool_spec_is_callable(self, agent, mock_handler):
        """Test ToolSpec function is the wrapper itself."""
        wrapper = SubagentToolWrapper(agent, mock_handler)
        spec = wrapper.to_tool_spec()

        result = spec.function()
        assert result["success"] is True


class TestToOpenAIFormat:
    """Test to_openai_format method."""

    @pytest.fixture
    def agent(self):
        return AgentDefinition(
            name="openai_agent",
            description="An agent for OpenAI format testing",
            prompt_config=PromptConfig(system_prompt="Test"),
            model_config=AgentModelConfig(model_name="gpt-4o"),
            input_config=InputConfig(
                fields=[
                    FieldDefinition(name="input", field_type="string"),
                ]
            ),
        )

    @pytest.fixture
    def mock_handler(self):
        def handler(agent_name, **kwargs):
            return {}

        return handler

    def test_to_openai_format(self, agent, mock_handler):
        """Test OpenAI format output."""
        wrapper = SubagentToolWrapper(agent, mock_handler)
        openai_format = wrapper.to_openai_format()

        assert openai_format["type"] == "function"
        assert openai_format["function"]["name"] == "agent_openai_agent"
        assert openai_format["function"]["description"] == "An agent for OpenAI format testing"
        assert "parameters" in openai_format["function"]


class TestInvocation:
    """Test wrapper invocation (calling the wrapper)."""

    @pytest.fixture
    def agent_with_inputs(self):
        return AgentDefinition(
            name="invoke_agent",
            description="Agent for invocation testing",
            prompt_config=PromptConfig(system_prompt="Test"),
            model_config=AgentModelConfig(model_name="gpt-4o"),
            input_config=InputConfig(
                fields=[
                    FieldDefinition(name="query", field_type="string", required=True),
                    FieldDefinition(name="count", field_type="integer", required=False),
                ]
            ),
        )

    def test_invoke_calls_handler(self, agent_with_inputs):
        """Test invocation calls the handler."""
        called_with = {}

        def handler(agent_name, **kwargs):
            called_with["agent_name"] = agent_name
            called_with["kwargs"] = kwargs
            return {"result": "success"}

        wrapper = SubagentToolWrapper(agent_with_inputs, handler)
        wrapper(query="test query")

        assert called_with["agent_name"] == "invoke_agent"
        assert called_with["kwargs"]["query"] == "test query"

    def test_invoke_returns_result(self, agent_with_inputs):
        """Test invocation returns handler result."""

        def handler(agent_name, **kwargs):
            return {"custom_data": "value"}

        wrapper = SubagentToolWrapper(agent_with_inputs, handler)
        result = wrapper(query="test")

        assert result["success"] is True
        assert result["custom_data"] == "value"
        assert result["agent_name"] == "invoke_agent"

    def test_invoke_missing_required_field(self, agent_with_inputs):
        """Test invocation fails for missing required field."""

        def handler(agent_name, **kwargs):
            return {"result": "should not reach"}

        wrapper = SubagentToolWrapper(agent_with_inputs, handler)
        result = wrapper()  # Missing 'query'

        assert result["success"] is False
        assert "Missing required field" in result["error"]

    def test_invoke_wrong_type(self, agent_with_inputs):
        """Test invocation fails for wrong type."""

        def handler(agent_name, **kwargs):
            return {"result": "should not reach"}

        wrapper = SubagentToolWrapper(agent_with_inputs, handler)
        result = wrapper(query="valid", count="not an integer")

        assert result["success"] is False
        assert "expected type" in result["error"]

    def test_invoke_handler_exception(self, agent_with_inputs):
        """Test invocation handles handler exceptions."""

        def handler(agent_name, **kwargs):
            raise ValueError("Handler error")

        wrapper = SubagentToolWrapper(agent_with_inputs, handler)
        result = wrapper(query="test")

        assert result["success"] is False
        assert "Handler error" in result["error"]

    def test_invoke_handler_non_dict_result(self, agent_with_inputs):
        """Test invocation wraps non-dict handler results."""

        def handler(agent_name, **kwargs):
            return "plain string result"

        wrapper = SubagentToolWrapper(agent_with_inputs, handler)
        result = wrapper(query="test")

        assert result["success"] is True
        assert result["result"] == "plain string result"


class TestTypeValidation:
    """Test input type validation."""

    @pytest.fixture
    def typed_agent(self):
        return AgentDefinition(
            name="typed_agent",
            description="Agent with various types",
            prompt_config=PromptConfig(system_prompt="Test"),
            model_config=AgentModelConfig(model_name="gpt-4o"),
            input_config=InputConfig(
                fields=[
                    FieldDefinition(name="text", field_type="string"),
                    FieldDefinition(name="number", field_type="integer"),
                    FieldDefinition(name="decimal", field_type="number"),
                    FieldDefinition(name="flag", field_type="boolean"),
                    FieldDefinition(name="items", field_type="array"),
                    FieldDefinition(name="data", field_type="object"),
                ]
            ),
        )

    @pytest.fixture
    def mock_handler(self):
        def handler(agent_name, **kwargs):
            return {"result": "ok"}

        return handler

    def test_valid_string(self, typed_agent, mock_handler):
        """Test valid string passes."""
        wrapper = SubagentToolWrapper(typed_agent, mock_handler)
        result = wrapper(
            text="hello",
            number=1,
            decimal=1.5,
            flag=True,
            items=[1, 2, 3],
            data={"key": "value"},
        )
        assert result["success"] is True

    def test_invalid_string(self, typed_agent, mock_handler):
        """Test invalid string fails."""
        wrapper = SubagentToolWrapper(typed_agent, mock_handler)
        result = wrapper(
            text=123,  # Should be string
            number=1,
            decimal=1.5,
            flag=True,
            items=[],
            data={},
        )
        assert result["success"] is False
        assert "text" in result["error"]

    def test_boolean_not_integer(self, typed_agent, mock_handler):
        """Test boolean is not accepted as integer."""
        wrapper = SubagentToolWrapper(typed_agent, mock_handler)
        result = wrapper(
            text="hello",
            number=True,  # Boolean, not integer
            decimal=1.5,
            flag=True,
            items=[],
            data={},
        )
        assert result["success"] is False


class TestCreateSubagentTools:
    """Test create_subagent_tools helper function."""

    def test_create_wrappers(self):
        """Test creating wrappers for multiple agents."""
        agents = [
            AgentDefinition(
                name="agent_a",
                description="Agent A",
                prompt_config=PromptConfig(system_prompt="Test"),
                model_config=AgentModelConfig(model_name="gpt-4o"),
            ),
            AgentDefinition(
                name="agent_b",
                description="Agent B",
                prompt_config=PromptConfig(system_prompt="Test"),
                model_config=AgentModelConfig(model_name="gpt-4o"),
            ),
        ]

        def handler(agent_name, **kwargs):
            return {}

        wrappers = create_subagent_tools(agents, handler)
        assert len(wrappers) == 2
        assert wrappers[0].name == "agent_agent_a"
        assert wrappers[1].name == "agent_agent_b"

    def test_skips_disabled_agents(self):
        """Test disabled agents are skipped."""
        agents = [
            AgentDefinition(
                name="enabled",
                description="Enabled agent",
                prompt_config=PromptConfig(system_prompt="Test"),
                model_config=AgentModelConfig(model_name="gpt-4o"),
                enabled=True,
            ),
            AgentDefinition(
                name="disabled",
                description="Disabled agent",
                prompt_config=PromptConfig(system_prompt="Test"),
                model_config=AgentModelConfig(model_name="gpt-4o"),
                enabled=False,
            ),
        ]

        def handler(agent_name, **kwargs):
            return {}

        wrappers = create_subagent_tools(agents, handler)
        assert len(wrappers) == 1
        assert wrappers[0].agent.name == "enabled"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
