from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from joshu.agents.definitions import AgentDefinition
from joshu.agents.exceptions import AgentNotFoundError, AgentValidationError
from joshu.agents.registry import AgentRegistry, get_agent_registry
from joshu.agents.schema_converter import input_config_to_json_schema
from joshu.core.tool_registry import ToolSpec

logger = logging.getLogger(__name__)


@dataclass
class DelegationRequest:
    """
    A validated request to delegate a task to a subagent.

    This is a pure data structure representing a validated delegation.
    Execution is handled elsewhere by the agent executor.

    Attributes:
        agent_name: Name of the target subagent
        agent: The resolved AgentDefinition
        inputs: Validated input parameters for the subagent
        task_description: Optional description of the delegated task
        metadata: Additional metadata for the delegation
    """

    agent_name: str
    agent: AgentDefinition
    inputs: Dict[str, Any]
    task_description: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "agent_name": self.agent_name,
            "inputs": self.inputs,
            "task_description": self.task_description,
            "metadata": self.metadata,
        }


class DelegateToAgentTool:
    """
    Tool that enables delegation to registered subagents.

    This tool dynamically generates its schema based on available subagents
    in the AgentRegistry. When called, it validates the delegation request
    and returns a DelegationRequest object for the executor to handle.

    Key behaviors:
    - Generates tool schema dynamically from registry
    - Validates agent exists and is enabled
    - Validates inputs against agent's InputConfig
    - Returns DelegationRequest (no execution)

    Example:
        >>> tool = DelegateToAgentTool()
        >>> request = tool.delegate("search_agent", query="find AI papers")
        >>> # request is a validated DelegationRequest, not execution result
    """

    TOOL_NAME = "delegate_to_agent"
    TOOL_DESCRIPTION = (
        "Delegate a task to a specialized subagent. "
        "Use this to invoke another agent's capabilities. "
        "Available agents and their inputs are listed in the parameters."
    )

    def __init__(self, registry: Optional[AgentRegistry] = None):
        """
        Initialize the delegation tool.

        Args:
            registry: AgentRegistry to use for agent discovery.
                     Defaults to global registry.
        """
        self._registry = registry or get_agent_registry()

    @property
    def name(self) -> str:
        """Tool name."""
        return self.TOOL_NAME

    @property
    def description(self) -> str:
        """Tool description including available agents."""
        agents = self._registry.get_available_agents(enabled_only=True)
        if not agents:
            return f"{self.TOOL_DESCRIPTION}\n\nNo agents currently available."

        agent_list = "\n".join(f"- {a.name}: {a.description}" for a in agents)
        return f"{self.TOOL_DESCRIPTION}\n\nAvailable agents:\n{agent_list}"

    def build_dynamic_schema(self) -> Dict[str, Any]:
        """
        Build a dynamic JSON Schema based on available subagents.

        Returns:
            JSON Schema with agent_name enum and dynamic oneOf for inputs
        """
        agents = self._registry.get_available_agents(enabled_only=True)
        agent_names = [a.name for a in agents]

        schema: Dict[str, Any] = {
            "type": "object",
            "properties": {
                "agent_name": {
                    "type": "string",
                    "description": "Name of the subagent to delegate to",
                    "enum": agent_names if agent_names else ["no_agents_available"],
                },
                "task_description": {
                    "type": "string",
                    "description": "Brief description of what you want the agent to do",
                },
                "inputs": {
                    "type": "object",
                    "description": "Input parameters for the selected agent",
                    "properties": {},
                },
            },
            "required": ["agent_name"],
        }

        # Add detailed input schemas for each agent as descriptions
        if agents:
            input_descriptions = []
            for agent in agents:
                if agent.input_config and agent.input_config.fields:
                    input_schema = input_config_to_json_schema(agent.input_config)
                    input_descriptions.append(f"{agent.name}: {input_schema['properties']}")
            if input_descriptions:
                schema["properties"]["inputs"]["description"] = (
                    "Input parameters vary by agent. Schemas: " + "; ".join(input_descriptions)
                )

        return schema

    def validate_delegation(
        self,
        agent_name: str,
        inputs: Optional[Dict[str, Any]] = None,
        task_description: Optional[str] = None,
    ) -> DelegationRequest:
        """
        Validate a delegation request and return a DelegationRequest.

        This method performs strict validation but NO execution.

        Args:
            agent_name: Name of the target subagent
            inputs: Input parameters for the subagent
            task_description: Optional description of the task

        Returns:
            Validated DelegationRequest object

        Raises:
            AgentNotFoundError: If agent doesn't exist or is disabled
            AgentValidationError: If inputs are invalid
        """
        inputs = inputs or {}

        # Resolve agent from registry
        try:
            agent = self._registry.get_agent(agent_name)
        except AgentNotFoundError:
            raise AgentNotFoundError(
                f"Cannot delegate to '{agent_name}': agent not found in registry. "
                f"Available: {self._registry.list_agents()}"
            )

        # Check if enabled
        if not agent.enabled:
            raise AgentValidationError(f"Cannot delegate to '{agent_name}': agent is disabled")

        # Validate inputs against agent's InputConfig
        if agent.input_config and agent.input_config.fields:
            validation_error = self._validate_inputs(agent, inputs)
            if validation_error:
                raise AgentValidationError(f"Invalid inputs for '{agent_name}': {validation_error}")

        # Build and return the validated request
        return DelegationRequest(
            agent_name=agent_name,
            agent=agent,
            inputs=inputs,
            task_description=task_description,
            metadata={
                "agent_version": agent.version,
                "agent_model": agent.model_config.model_name,
            },
        )

    def _validate_inputs(self, agent: AgentDefinition, inputs: Dict[str, Any]) -> Optional[str]:
        """
        Validate inputs against agent's InputConfig.

        Returns:
            Error message if invalid, None if valid
        """
        if not agent.input_config:
            return None

        # Check required fields
        for field_def in agent.input_config.fields:
            if field_def.required and field_def.name not in inputs:
                return f"Missing required input: {field_def.name}"

            # Type validation
            if field_def.name in inputs:
                value = inputs[field_def.name]
                type_error = self._check_type(field_def.name, value, field_def.field_type)
                if type_error:
                    return type_error

        return None

    def _check_type(self, name: str, value: Any, expected: str) -> Optional[str]:
        """Check if value matches expected type."""
        checks = {
            "string": lambda v: isinstance(v, str),
            "integer": lambda v: isinstance(v, int) and not isinstance(v, bool),
            "number": lambda v: isinstance(v, (int, float)) and not isinstance(v, bool),
            "boolean": lambda v: isinstance(v, bool),
            "array": lambda v: isinstance(v, list),
            "object": lambda v: isinstance(v, dict),
        }
        if expected in checks and not checks[expected](value):
            return f"Input '{name}' expected {expected}, got {type(value).__name__}"
        return None

    def to_tool_spec(self) -> ToolSpec:
        """
        Convert to ToolSpec for registration with ToolRegistry.

        Note: The function returns DelegationRequest, not execution results.
        The executor must handle the actual invocation.

        Returns:
            ToolSpec instance
        """
        return ToolSpec(
            name=self.name,
            description=self.description,
            parameters=self.build_dynamic_schema(),
            function=self._tool_function,
            enabled=True,
            requires_approval=False,
        )

    def _tool_function(
        self,
        agent_name: str,
        inputs: Optional[Dict[str, Any]] = None,
        task_description: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Tool function that creates validated DelegationRequest.

        Returns a dictionary representation for LLM consumption.
        Actual execution happens in the agent executor.
        """
        try:
            request = self.validate_delegation(agent_name, inputs, task_description)
            return {
                "success": True,
                "delegation_request": request.to_dict(),
                "message": f"Delegation to '{agent_name}' validated. Ready for execution.",
            }
        except (AgentNotFoundError, AgentValidationError) as e:
            return {
                "success": False,
                "error": str(e),
                "message": f"Delegation to '{agent_name}' failed validation.",
            }

    def get_agents_for_prompt(self) -> str:
        """
        Generate a prompt snippet listing available agents.

        Useful for including in system prompts.

        Returns:
            Formatted string describing available agents
        """
        agents = self._registry.get_available_agents(enabled_only=True)
        if not agents:
            return "No subagents available for delegation."

        lines = ["You can delegate to the following subagents:"]
        for agent in agents:
            lines.append(f"\n{agent.to_system_prompt_snippet()}")
        return "\n".join(lines)


def create_delegate_tool(registry: Optional[AgentRegistry] = None) -> ToolSpec:
    """
    Convenience function to create and return a delegation tool spec.

    Args:
        registry: Optional AgentRegistry to use

    Returns:
        ToolSpec ready for registration
    """
    tool = DelegateToAgentTool(registry)
    return tool.to_tool_spec()
