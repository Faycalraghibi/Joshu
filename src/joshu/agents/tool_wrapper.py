"""
SubagentToolWrapper for exposing agents as callable tools.

This module provides the SubagentToolWrapper that wraps an AgentDefinition
and exposes it as a DeclarativeTool, making agents indistinguishable from
normal tools from the runtime's perspective.
"""

from __future__ import annotations

import logging
from typing import Any, Callable, Dict, Optional

from joshu.agents.definitions import AgentDefinition
from joshu.agents.exceptions import AgentValidationError, SchemaConversionError
from joshu.agents.schema_converter import input_config_to_json_schema
from joshu.core.tool_registry import ToolSpec

logger = logging.getLogger(__name__)


class SubagentToolWrapper:
    """
    Wraps an AgentDefinition and exposes it as a DeclarativeTool.

    This adapter converts an agent into a tool that can be registered
    with the ToolRegistry and invoked like any other tool. From the
    runtime's perspective, a subagent is indistinguishable from a
    regular tool.

    Responsibilities:
    - Convert the agent's InputConfig → JSON Schema
    - Generate tool metadata (name, description, parameters)
    - Bind to a subagent invocation handler
    - Validate inputs before delegation

    Example:
        >>> def invoke_handler(agent_name: str, **kwargs):
        ...     # Actual execution handled by executor
        ...     return {"result": "executed"}
        >>> wrapper = SubagentToolWrapper(agent_def, invoke_handler)
        >>> tool_spec = wrapper.to_tool_spec()
        >>> registry.register(tool_spec)
    """

    def __init__(
        self,
        agent: AgentDefinition,
        invocation_handler: Callable[..., Dict[str, Any]],
        tool_name_prefix: str = "agent_",
    ):
        """
        Initialize the SubagentToolWrapper.

        Args:
            agent: The agent definition to wrap
            invocation_handler: Callable that will be invoked when the tool is called.
                Signature: (agent_name: str, **validated_inputs) -> Dict[str, Any]
            tool_name_prefix: Prefix for the generated tool name (default: "agent_")

        Raises:
            AgentValidationError: If the agent definition is invalid
        """
        if not agent.validate():
            raise AgentValidationError(f"Cannot wrap invalid agent: {agent.name}")

        self._agent = agent
        self._invocation_handler = invocation_handler
        self._tool_name_prefix = tool_name_prefix
        self._json_schema = self._build_schema()

    @property
    def agent(self) -> AgentDefinition:
        """Get the wrapped agent definition."""
        return self._agent

    @property
    def name(self) -> str:
        """
        Get the tool name derived from agent name.

        Returns:
            Tool name with prefix (e.g., "agent_my_agent")
        """
        return f"{self._tool_name_prefix}{self._agent.name}"

    @property
    def description(self) -> str:
        """
        Get the tool description from agent.

        Returns:
            Agent description for use as tool description
        """
        return self._agent.description

    @property
    def parameters(self) -> Dict[str, Any]:
        """
        Get the JSON Schema parameters for this tool.

        Returns:
            JSON Schema object describing tool parameters
        """
        return self._json_schema

    def _build_schema(self) -> Dict[str, Any]:
        """
        Build JSON Schema from agent's InputConfig.

        Returns:
            JSON Schema object

        Raises:
            SchemaConversionError: If schema conversion fails
        """
        if self._agent.input_config:
            try:
                return input_config_to_json_schema(self._agent.input_config)
            except SchemaConversionError:
                logger.error(f"Failed to build schema for agent {self._agent.name}")
                raise
        else:
            # No input config means no parameters
            return {
                "type": "object",
                "properties": {},
            }

    def to_tool_spec(self) -> ToolSpec:
        """
        Convert to ToolSpec for registration with ToolRegistry.

        Returns:
            ToolSpec instance ready for registration
        """
        return ToolSpec(
            name=self.name,
            description=self.description,
            parameters=self.parameters,
            function=self,  # The wrapper itself is callable
            enabled=self._agent.enabled,
            requires_approval=False,
        )

    def to_openai_format(self) -> Dict[str, Any]:
        """
        Convert to OpenAI function calling format.

        Returns:
            Tool definition in OpenAI format
        """
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }

    def __call__(self, **kwargs: Any) -> Dict[str, Any]:
        """
        Execute the wrapped agent through the invocation handler.

        This method makes the wrapper callable, allowing it to be used
        as the function in a ToolSpec.

        Args:
            **kwargs: Validated input parameters for the agent

        Returns:
            Dictionary containing:
                - success: bool indicating if invocation was successful
                - result: The agent's response (if successful)
                - error: Error message (if failed)
                - agent_name: Name of the invoked agent
        """
        logger.info(f"Invoking subagent: {self._agent.name} with args: {kwargs}")

        # Validate inputs if we have a schema
        if self._agent.input_config and self._agent.input_config.fields:
            validation_error = self._validate_inputs(kwargs)
            if validation_error:
                logger.warning(
                    f"Input validation failed for {self._agent.name}: {validation_error}"
                )
                return {
                    "success": False,
                    "result": None,
                    "error": validation_error,
                    "agent_name": self._agent.name,
                }

        # Delegate to the invocation handler
        try:
            result = self._invocation_handler(self._agent.name, **kwargs)

            # Ensure result is a dict
            if not isinstance(result, dict):
                result = {"result": result}

            # Add success flag if not present
            if "success" not in result:
                result["success"] = True

            result["agent_name"] = self._agent.name
            return result

        except Exception as e:
            logger.error(f"Subagent invocation failed: {e}", exc_info=True)
            return {
                "success": False,
                "result": None,
                "error": f"Subagent invocation failed: {str(e)}",
                "agent_name": self._agent.name,
            }

    def _validate_inputs(self, inputs: Dict[str, Any]) -> Optional[str]:
        """
        Validate inputs against the agent's InputConfig.

        Args:
            inputs: The input dictionary to validate

        Returns:
            Error message string if validation fails, None if valid
        """
        if not self._agent.input_config:
            return None

        # Check required fields
        for field in self._agent.input_config.fields:
            if field.required and field.name not in inputs:
                return f"Missing required field: {field.name}"

            if field.name in inputs:
                value = inputs[field.name]
                type_error = self._validate_field_type(field.name, value, field.field_type)
                if type_error:
                    return type_error

        return None

    def _validate_field_type(
        self, field_name: str, value: Any, expected_type: str
    ) -> Optional[str]:
        """
        Validate that a value matches the expected type.

        Args:
            field_name: Name of the field for error messages
            value: The value to validate
            expected_type: Expected type string

        Returns:
            Error message if type mismatch, None if valid
        """
        type_checks = {
            "string": lambda v: isinstance(v, str),
            "integer": lambda v: isinstance(v, int) and not isinstance(v, bool),
            "number": lambda v: isinstance(v, (int, float)) and not isinstance(v, bool),
            "boolean": lambda v: isinstance(v, bool),
            "array": lambda v: isinstance(v, list),
            "object": lambda v: isinstance(v, dict),
        }

        if expected_type in type_checks:
            if not type_checks[expected_type](value):
                return f"Field '{field_name}' expected type '{expected_type}', got '{type(value).__name__}'"

        return None

    def __repr__(self) -> str:
        return f"SubagentToolWrapper(agent={self._agent.name!r}, enabled={self._agent.enabled})"


def create_subagent_tools(
    agents: list[AgentDefinition],
    invocation_handler: Callable[..., Dict[str, Any]],
) -> list[SubagentToolWrapper]:
    """
    Create SubagentToolWrapper instances for a list of agents.

    Args:
        agents: List of agent definitions to wrap
        invocation_handler: Handler for subagent invocation

    Returns:
        List of SubagentToolWrapper instances
    """
    wrappers = []
    for agent in agents:
        if not agent.enabled:
            logger.debug(f"Skipping disabled agent: {agent.name}")
            continue

        try:
            wrapper = SubagentToolWrapper(agent, invocation_handler)
            wrappers.append(wrapper)
            logger.debug(f"Created wrapper for agent: {agent.name}")
        except (AgentValidationError, SchemaConversionError) as e:
            logger.error(f"Failed to create wrapper for agent {agent.name}: {e}")

    return wrappers
