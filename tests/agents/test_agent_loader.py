"""
Unit tests for AgentLoader implementations.

Run with: pytest tests/agents/test_agent_loader.py -v
"""

import json
import tempfile
from pathlib import Path

import pytest

from joshu.agents.definitions import AgentDefinition, AgentModelConfig, PromptConfig
from joshu.agents.loader import (
    CompositeAgentLoader,
    JsonAgentLoader,
    load_agents_from_path,
)


class TestJsonAgentLoader:
    """Test JsonAgentLoader functionality."""

    @pytest.fixture
    def valid_agent_dict(self) -> dict:
        """Create a valid agent dictionary."""
        return {
            "name": "test_agent",
            "description": "A test agent",
            "prompt_config": {"system_prompt": "You are a test."},
            "model_config": {"model_name": "gpt-4o"},
        }

    def test_supports_json_extension(self):
        """Test loader supports .json extension."""
        loader = JsonAgentLoader()
        assert loader.supports_extension(".json")
        assert loader.supports_extension(".JSON")
        assert not loader.supports_extension(".yaml")

    def test_load_from_string_single(self, valid_agent_dict):
        """Test loading single agent from JSON string."""
        loader = JsonAgentLoader()
        content = json.dumps(valid_agent_dict)
        agents = loader.load_from_string(content)

        assert len(agents) == 1
        assert agents[0].name == "test_agent"

    def test_load_from_string_array(self, valid_agent_dict):
        """Test loading multiple agents from JSON array."""
        loader = JsonAgentLoader()
        agent2 = valid_agent_dict.copy()
        agent2["name"] = "second_agent"

        content = json.dumps([valid_agent_dict, agent2])
        agents = loader.load_from_string(content)

        assert len(agents) == 2
        assert agents[0].name == "test_agent"
        assert agents[1].name == "second_agent"

    def test_load_from_file(self, valid_agent_dict):
        """Test loading agents from a JSON file."""
        loader = JsonAgentLoader()

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, encoding="utf-8"
        ) as f:
            json.dump(valid_agent_dict, f)
            f.flush()

            agents = loader.load_from_path(Path(f.name))
            assert len(agents) == 1
            assert agents[0].name == "test_agent"

    def test_load_from_directory(self, valid_agent_dict):
        """Test loading agents from a directory."""
        loader = JsonAgentLoader()

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create two JSON files
            path1 = Path(tmpdir) / "agent1.json"
            path1.write_text(json.dumps(valid_agent_dict), encoding="utf-8")

            agent2 = valid_agent_dict.copy()
            agent2["name"] = "agent_two"
            path2 = Path(tmpdir) / "agent2.json"
            path2.write_text(json.dumps(agent2), encoding="utf-8")

            agents = loader.load_from_path(Path(tmpdir))
            assert len(agents) == 2

    def test_load_invalid_json_raises(self):
        """Test loading invalid JSON raises error."""
        loader = JsonAgentLoader()

        with pytest.raises(Exception):
            loader.load_from_string("not valid json")

    def test_load_nonexistent_path_raises(self):
        """Test loading from nonexistent path raises."""
        loader = JsonAgentLoader()

        with pytest.raises(FileNotFoundError):
            loader.load_from_path(Path("/nonexistent/path.json"))


class TestCompositeAgentLoader:
    """Test CompositeAgentLoader functionality."""

    def test_supports_json_and_yaml(self):
        """Test composite loader supports both formats."""
        loader = CompositeAgentLoader()
        assert loader.supports_extension(".json")
        assert loader.supports_extension(".yaml")
        assert loader.supports_extension(".yml")

    def test_load_json_file(self):
        """Test loading JSON file through composite loader."""
        loader = CompositeAgentLoader()
        agent_dict = {
            "name": "composite_test",
            "description": "Test agent",
            "prompt_config": {"system_prompt": "Test."},
            "model_config": {"model_name": "gpt-4o"},
        }

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, encoding="utf-8"
        ) as f:
            json.dump(agent_dict, f)
            f.flush()

            agents = loader.load_from_path(Path(f.name))
            assert len(agents) == 1
            assert agents[0].name == "composite_test"


class TestLoadAgentsFromPath:
    """Test load_agents_from_path convenience function."""

    def test_load_from_json_file(self):
        """Test convenience function with JSON file."""
        agent_dict = {
            "name": "convenience_test",
            "description": "Test agent",
            "prompt_config": {"system_prompt": "Test."},
            "model_config": {"model_name": "gpt-4o"},
        }

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, encoding="utf-8"
        ) as f:
            json.dump(agent_dict, f)
            f.flush()

            agents = load_agents_from_path(f.name)
            assert len(agents) == 1
            assert agents[0].name == "convenience_test"


class TestDescriptionGenerators:
    """Test agent description generator methods."""

    @pytest.fixture
    def full_agent(self):
        """Create a fully configured agent."""
        from joshu.agents.definitions import (
            FieldDefinition,
            InputConfig,
            OutputConfig,
            ToolConfig,
        )

        return AgentDefinition(
            name="research_agent",
            description="Researches topics and provides summaries",
            prompt_config=PromptConfig(system_prompt="You are a research assistant."),
            model_config=AgentModelConfig(model_name="gpt-4o"),
            tool_config=ToolConfig(allowed_tools=["web_search", "web_fetch"]),
            input_config=InputConfig(
                fields=[
                    FieldDefinition(name="topic", field_type="string", required=True),
                    FieldDefinition(name="depth", field_type="integer", required=False, default=3),
                ]
            ),
            output_config=OutputConfig(
                fields=[
                    FieldDefinition(name="summary", field_type="string"),
                    FieldDefinition(name="sources", field_type="array"),
                ]
            ),
        )

    def test_to_tool_description(self, full_agent):
        """Test tool description generation."""
        desc = full_agent.to_tool_description()

        assert "**research_agent**" in desc
        assert "Researches topics" in desc
        assert "`topic`" in desc
        assert "**Required**" in desc
        assert "`depth`" in desc
        assert "**Optional**" in desc

    def test_to_tool_description_no_inputs(self):
        """Test tool description with no inputs."""
        agent = AgentDefinition(
            name="simple_agent",
            description="Simple agent",
            prompt_config=PromptConfig(system_prompt="Test."),
            model_config=AgentModelConfig(model_name="gpt-4o"),
        )
        desc = agent.to_tool_description()

        assert "**Inputs**: None" in desc

    def test_to_system_prompt_snippet(self, full_agent):
        """Test system prompt snippet generation."""
        snippet = full_agent.to_system_prompt_snippet()

        assert "Agent: research_agent" in snippet
        assert "Purpose: Researches topics" in snippet
        assert "topic*: string" in snippet  # * marks required
        assert "depth: integer" in snippet
        assert "Tools: web_search, web_fetch" in snippet

    def test_to_invocation_summary(self, full_agent):
        """Test invocation summary generation."""
        summary = full_agent.to_invocation_summary()

        assert summary["name"] == "research_agent"
        assert summary["model"] == "gpt-4o"
        assert "topic" in summary["inputs"]["required"]
        assert "depth" in summary["inputs"]["optional"]
        assert "summary" in summary["outputs"]
        assert "web_search" in summary["tools"]


class TestModelAliasResolution:
    """Test model alias resolution at registration."""

    def setup_method(self):
        """Clear registry before each test."""
        from joshu.agents.registry import AgentRegistry

        registry = AgentRegistry()
        registry.clear()

    def teardown_method(self):
        """Clear registry after each test."""
        from joshu.agents.registry import AgentRegistry

        registry = AgentRegistry()
        registry.clear()

    def test_resolve_alias_at_registration(self):
        """Test model alias is resolved during registration."""
        from joshu.agents.registry import AgentRegistry

        registry = AgentRegistry()
        registry.apply_config_overrides(
            {"model_aliases": {"fast": "gpt-4o-mini", "smart": "gpt-4o"}}
        )

        agent = AgentDefinition(
            name="aliased_agent",
            description="Agent with alias",
            prompt_config=PromptConfig(system_prompt="Test."),
            model_config=AgentModelConfig(
                model_name="fast",
                fallback_models=["smart"],
            ),
        )

        registry.register(agent)

        registered = registry.get_agent("aliased_agent")
        assert registered.model_config.model_name == "gpt-4o-mini"
        assert registered.model_config.fallback_models == ["gpt-4o"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
