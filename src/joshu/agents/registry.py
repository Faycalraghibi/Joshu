"""
Agent Registry for managing agent definitions.

This module provides an AgentRegistry that is the single source of truth
for registered agents. It handles:
- Discovery of agent definitions from configured sources
- Validation of agent definitions
- Global configuration overrides (enable/disable, model aliases)
- Read-only access to registered agents
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from joshu.agents.definitions import AgentDefinition, AgentModelConfig
from joshu.agents.exceptions import (
    AgentNotFoundError,
    AgentRegistrationError,
    AgentValidationError,
)

logger = logging.getLogger(__name__)


class AgentRegistry:
    """
    Central registry for managing agent definitions.

    This class maintains a collection of registered agent definitions
    and provides methods for discovering, validating, and accessing them.

    Guarantees:
    - Only validated agents are registered
    - Duplicate agent names are rejected
    - Registry is the single source of truth for agents
    """

    _instance: Optional["AgentRegistry"] = None
    _agents: Dict[str, AgentDefinition]

    def __new__(cls) -> "AgentRegistry":
        """Ensure singleton instance."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._agents = {}
            cls._instance._model_aliases: Dict[str, str] = {}
        return cls._instance

    def register(
        self,
        agent: AgentDefinition,
        allow_overwrite: bool = False,
        resolve_model_aliases: bool = True,
    ) -> bool:
        """
        Register an agent definition.

        Args:
            agent: The agent definition to register
            allow_overwrite: If True, allows overwriting existing agents
            resolve_model_aliases: If True, resolve model aliases at registration

        Returns:
            True if registration was successful

        Raises:
            AgentValidationError: If the agent fails validation
            AgentRegistrationError: If an agent with the same name already exists
        """
        # Validate the agent
        if not agent.validate():
            raise AgentValidationError(f"Agent '{agent.name}' failed validation")

        # Resolve model aliases at registration time
        if resolve_model_aliases and self._model_aliases:
            resolved_model = self.resolve_model_alias(agent.model_config.model_name)
            if resolved_model != agent.model_config.model_name:
                logger.info(
                    f"Resolved model alias '{agent.model_config.model_name}' -> '{resolved_model}' "
                    f"for agent '{agent.name}'"
                )
                # Create updated agent with resolved model
                agent = AgentDefinition(
                    name=agent.name,
                    description=agent.description,
                    prompt_config=agent.prompt_config,
                    model_config=AgentModelConfig(
                        model_name=resolved_model,
                        fallback_models=[
                            self.resolve_model_alias(m) for m in agent.model_config.fallback_models
                        ],
                    ),
                    run_config=agent.run_config,
                    tool_config=agent.tool_config,
                    input_config=agent.input_config,
                    output_config=agent.output_config,
                    enabled=agent.enabled,
                    version=agent.version,
                )

        # Check for duplicates
        if agent.name in self._agents and not allow_overwrite:
            raise AgentRegistrationError(
                f"Agent '{agent.name}' is already registered. Use allow_overwrite=True to replace."
            )

        if agent.name in self._agents:
            logger.warning(f"Overwriting agent: {agent.name}")

        self._agents[agent.name] = agent
        logger.info(f"Registered agent: {agent.name}")
        return True

    def unregister(self, agent_name: str) -> bool:
        """
        Unregister an agent.

        Args:
            agent_name: Name of the agent to unregister

        Returns:
            True if unregistration was successful, False if agent not found
        """
        if agent_name not in self._agents:
            logger.warning(f"Agent '{agent_name}' not found in registry")
            return False

        del self._agents[agent_name]
        logger.info(f"Unregistered agent: {agent_name}")
        return True

    def get_agent(self, agent_name: str) -> AgentDefinition:
        """
        Get an agent by name.

        Args:
            agent_name: Name of the agent to retrieve

        Returns:
            The agent definition

        Raises:
            AgentNotFoundError: If the agent is not registered
        """
        if agent_name not in self._agents:
            raise AgentNotFoundError(f"Agent '{agent_name}' not found in registry")
        return self._agents[agent_name]

    def get_agent_or_none(self, agent_name: str) -> Optional[AgentDefinition]:
        """
        Get an agent by name, returning None if not found.

        Args:
            agent_name: Name of the agent to retrieve

        Returns:
            The agent definition or None if not found
        """
        return self._agents.get(agent_name)

    def get_available_agents(self, enabled_only: bool = True) -> List[AgentDefinition]:
        """
        Get list of available agents.

        Args:
            enabled_only: If True, only return enabled agents

        Returns:
            List of agent definitions
        """
        if enabled_only:
            return [agent for agent in self._agents.values() if agent.enabled]
        return list(self._agents.values())

    def list_agents(self) -> List[str]:
        """
        Get list of all registered agent names.

        Returns:
            List of agent names
        """
        return list(self._agents.keys())

    def apply_config_overrides(self, overrides: Dict[str, Any]) -> None:
        """
        Apply global configuration overrides to registered agents.

        Supports:
        - enable/disable agents by name
        - model alias resolution

        Args:
            overrides: Dictionary with configuration overrides
                {
                    "disabled_agents": ["agent1", "agent2"],
                    "enabled_agents": ["agent3"],  # Re-enable previously disabled
                    "model_aliases": {"alias": "actual_model_name"}
                }
        """
        # Handle disabled agents
        disabled_agents = overrides.get("disabled_agents", [])
        for agent_name in disabled_agents:
            if agent_name in self._agents:
                # Create a new definition with enabled=False
                agent = self._agents[agent_name]
                self._agents[agent_name] = AgentDefinition(
                    name=agent.name,
                    description=agent.description,
                    prompt_config=agent.prompt_config,
                    model_config=agent.model_config,
                    run_config=agent.run_config,
                    tool_config=agent.tool_config,
                    input_config=agent.input_config,
                    output_config=agent.output_config,
                    enabled=False,
                    version=agent.version,
                )
                logger.info(f"Disabled agent: {agent_name}")

        # Handle enabled agents
        enabled_agents = overrides.get("enabled_agents", [])
        for agent_name in enabled_agents:
            if agent_name in self._agents:
                agent = self._agents[agent_name]
                self._agents[agent_name] = AgentDefinition(
                    name=agent.name,
                    description=agent.description,
                    prompt_config=agent.prompt_config,
                    model_config=agent.model_config,
                    run_config=agent.run_config,
                    tool_config=agent.tool_config,
                    input_config=agent.input_config,
                    output_config=agent.output_config,
                    enabled=True,
                    version=agent.version,
                )
                logger.info(f"Enabled agent: {agent_name}")

        # Store model aliases for resolution
        model_aliases = overrides.get("model_aliases", {})
        self._model_aliases.update(model_aliases)
        if model_aliases:
            logger.info(f"Applied {len(model_aliases)} model aliases")

    def resolve_model_alias(self, model_name: str) -> str:
        """
        Resolve a model alias to the actual model name.

        Args:
            model_name: Model name or alias

        Returns:
            Resolved model name
        """
        return self._model_aliases.get(model_name, model_name)

    def discover_from_source(
        self,
        source: Union[str, Path],
        allow_overwrite: bool = False,
    ) -> int:
        """
        Discover and register agents from a source path.

        Uses the CompositeAgentLoader to load agents from files.

        Args:
            source: Path to file or directory containing agent definitions
            allow_overwrite: If True, allows overwriting existing agents

        Returns:
            Number of agents discovered and registered
        """
        from joshu.agents.loader import load_agents_from_path

        try:
            agents = load_agents_from_path(source)
            count = 0
            for agent in agents:
                try:
                    self.register(agent, allow_overwrite=allow_overwrite)
                    count += 1
                except AgentRegistrationError as e:
                    logger.warning(f"Skipping agent: {e}")
            logger.info(f"Discovered and registered {count} agents from {source}")
            return count
        except FileNotFoundError:
            logger.error(f"Source path not found: {source}")
            return 0
        except Exception as e:
            logger.error(f"Failed to discover agents from {source}: {e}")
            return 0

    def clear(self) -> None:
        """Clear all registered agents (mainly for testing)."""
        self._agents.clear()
        self._model_aliases.clear()
        logger.info("Cleared all registered agents")


# Module-level variable for singleton
_registry: Optional[AgentRegistry] = None


def get_agent_registry() -> AgentRegistry:
    """
    Get the global agent registry instance.

    Returns:
        AgentRegistry singleton instance
    """
    global _registry
    if _registry is None:
        _registry = AgentRegistry()
    return _registry
