"""
Unit tests for AgentRegistry.

Run with: pytest tests/agents/test_agent_registry.py -v
"""

import pytest

from joshu.agents.definitions import (
    AgentDefinition,
    AgentModelConfig,
    PromptConfig,
)
from joshu.agents.exceptions import (
    AgentNotFoundError,
    AgentRegistrationError,
    AgentValidationError,
)
from joshu.agents.registry import AgentRegistry, get_agent_registry


class TestAgentRegistry:
    """Test AgentRegistry functionality."""

    def setup_method(self):
        """Clear registry before each test."""
        registry = AgentRegistry()
        registry.clear()

    def teardown_method(self):
        """Clear registry after each test."""
        registry = AgentRegistry()
        registry.clear()

    @pytest.fixture
    def valid_agent(self):
        """Create a valid agent definition for testing."""
        return AgentDefinition(
            name="test_agent",
            description="A test agent for unit testing",
            prompt_config=PromptConfig(system_prompt="You are a test assistant."),
            model_config=AgentModelConfig(model_name="gpt-4o"),
        )

    @pytest.fixture
    def another_agent(self):
        """Create another valid agent definition."""
        return AgentDefinition(
            name="another_agent",
            description="Another test agent",
            prompt_config=PromptConfig(system_prompt="You are another assistant."),
            model_config=AgentModelConfig(model_name="claude-3-sonnet"),
        )

    def test_singleton_pattern(self):
        """Test registry is a singleton."""
        registry1 = AgentRegistry()
        registry2 = AgentRegistry()
        assert registry1 is registry2

    def test_register_valid_agent(self, valid_agent):
        """Test registering a valid agent."""
        registry = AgentRegistry()
        result = registry.register(valid_agent)
        assert result is True
        assert "test_agent" in registry.list_agents()

    def test_register_invalid_agent_raises(self):
        """Test registering an invalid agent raises AgentValidationError."""
        invalid_agent = AgentDefinition(
            name="",  # Invalid: empty name
            description="A test agent",
            prompt_config=PromptConfig(system_prompt="Test"),
            model_config=AgentModelConfig(model_name="gpt-4o"),
        )
        registry = AgentRegistry()
        with pytest.raises(AgentValidationError):
            registry.register(invalid_agent)

    def test_reject_duplicate_agent(self, valid_agent):
        """Test duplicate agent names are rejected."""
        registry = AgentRegistry()
        registry.register(valid_agent)

        duplicate = AgentDefinition(
            name="test_agent",  # Same name
            description="A duplicate agent",
            prompt_config=PromptConfig(system_prompt="Test"),
            model_config=AgentModelConfig(model_name="gpt-4o"),
        )
        with pytest.raises(AgentRegistrationError):
            registry.register(duplicate)

    def test_overwrite_allowed(self, valid_agent):
        """Test overwriting existing agent with allow_overwrite=True."""
        registry = AgentRegistry()
        registry.register(valid_agent)

        updated = AgentDefinition(
            name="test_agent",
            description="Updated description",
            prompt_config=PromptConfig(system_prompt="Updated prompt"),
            model_config=AgentModelConfig(model_name="gpt-4o"),
        )
        result = registry.register(updated, allow_overwrite=True)
        assert result is True

        agent = registry.get_agent("test_agent")
        assert agent.description == "Updated description"

    def test_get_agent_success(self, valid_agent):
        """Test getting a registered agent."""
        registry = AgentRegistry()
        registry.register(valid_agent)

        agent = registry.get_agent("test_agent")
        assert agent.name == "test_agent"
        assert agent.description == "A test agent for unit testing"

    def test_get_agent_not_found_raises(self):
        """Test getting non-existent agent raises AgentNotFoundError."""
        registry = AgentRegistry()
        with pytest.raises(AgentNotFoundError):
            registry.get_agent("nonexistent")

    def test_get_agent_or_none_returns_none(self):
        """Test get_agent_or_none returns None for non-existent agent."""
        registry = AgentRegistry()
        result = registry.get_agent_or_none("nonexistent")
        assert result is None

    def test_get_agent_or_none_returns_agent(self, valid_agent):
        """Test get_agent_or_none returns agent when found."""
        registry = AgentRegistry()
        registry.register(valid_agent)

        result = registry.get_agent_or_none("test_agent")
        assert result is not None
        assert result.name == "test_agent"

    def test_unregister_agent(self, valid_agent):
        """Test unregistering an agent."""
        registry = AgentRegistry()
        registry.register(valid_agent)

        result = registry.unregister("test_agent")
        assert result is True
        assert "test_agent" not in registry.list_agents()

    def test_unregister_nonexistent_returns_false(self):
        """Test unregistering non-existent agent returns False."""
        registry = AgentRegistry()
        result = registry.unregister("nonexistent")
        assert result is False

    def test_list_agents(self, valid_agent, another_agent):
        """Test listing all registered agents."""
        registry = AgentRegistry()
        registry.register(valid_agent)
        registry.register(another_agent)

        agents = registry.list_agents()
        assert len(agents) == 2
        assert "test_agent" in agents
        assert "another_agent" in agents

    def test_get_available_agents_enabled_only(self, valid_agent, another_agent):
        """Test get_available_agents filters disabled agents."""
        registry = AgentRegistry()
        registry.register(valid_agent)

        disabled_agent = AgentDefinition(
            name="disabled_agent",
            description="A disabled agent",
            prompt_config=PromptConfig(system_prompt="Test"),
            model_config=AgentModelConfig(model_name="gpt-4o"),
            enabled=False,
        )
        registry.register(disabled_agent)

        available = registry.get_available_agents(enabled_only=True)
        assert len(available) == 1
        assert available[0].name == "test_agent"

    def test_get_available_agents_include_disabled(self, valid_agent):
        """Test get_available_agents includes disabled when requested."""
        registry = AgentRegistry()
        registry.register(valid_agent)

        disabled_agent = AgentDefinition(
            name="disabled_agent",
            description="A disabled agent",
            prompt_config=PromptConfig(system_prompt="Test"),
            model_config=AgentModelConfig(model_name="gpt-4o"),
            enabled=False,
        )
        registry.register(disabled_agent)

        available = registry.get_available_agents(enabled_only=False)
        assert len(available) == 2

    def test_clear_registry(self, valid_agent, another_agent):
        """Test clearing the registry."""
        registry = AgentRegistry()
        registry.register(valid_agent)
        registry.register(another_agent)

        registry.clear()
        assert len(registry.list_agents()) == 0


class TestConfigOverrides:
    """Test configuration override functionality."""

    def setup_method(self):
        """Clear registry before each test."""
        registry = AgentRegistry()
        registry.clear()

    def teardown_method(self):
        """Clear registry after each test."""
        registry = AgentRegistry()
        registry.clear()

    @pytest.fixture
    def sample_agents(self):
        """Create sample agents for testing."""
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
        return agents

    def test_disable_agents(self, sample_agents):
        """Test disabling agents via overrides."""
        registry = AgentRegistry()
        for agent in sample_agents:
            registry.register(agent)

        registry.apply_config_overrides({"disabled_agents": ["agent_a"]})

        agent_a = registry.get_agent("agent_a")
        agent_b = registry.get_agent("agent_b")
        assert agent_a.enabled is False
        assert agent_b.enabled is True

    def test_enable_disabled_agents(self, sample_agents):
        """Test enabling previously disabled agents."""
        registry = AgentRegistry()
        for agent in sample_agents:
            registry.register(agent)

        # Disable first
        registry.apply_config_overrides({"disabled_agents": ["agent_a"]})

        # Re-enable
        registry.apply_config_overrides({"enabled_agents": ["agent_a"]})

        agent_a = registry.get_agent("agent_a")
        assert agent_a.enabled is True

    def test_model_alias_resolution(self):
        """Test model alias resolution."""
        registry = AgentRegistry()
        registry.apply_config_overrides(
            {
                "model_aliases": {
                    "fast": "gpt-4o-mini",
                    "smart": "gpt-4o",
                }
            }
        )

        assert registry.resolve_model_alias("fast") == "gpt-4o-mini"
        assert registry.resolve_model_alias("smart") == "gpt-4o"
        assert registry.resolve_model_alias("unknown") == "unknown"


class TestGetAgentRegistry:
    """Test get_agent_registry function."""

    def teardown_method(self):
        """Clear registry after each test."""
        registry = get_agent_registry()
        registry.clear()

    def test_get_agent_registry_returns_singleton(self):
        """Test get_agent_registry returns singleton instance."""
        registry1 = get_agent_registry()
        registry2 = get_agent_registry()
        assert registry1 is registry2

    def test_get_agent_registry_same_as_constructor(self):
        """Test get_agent_registry returns same instance as constructor."""
        registry1 = get_agent_registry()
        registry2 = AgentRegistry()
        assert registry1 is registry2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
