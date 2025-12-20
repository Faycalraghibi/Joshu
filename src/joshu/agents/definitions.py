"""
Core data structures for Agent Definitions.

This module provides the dataclasses that form the declarative contract
for agent definitions. These structures describe agents but do not execute them.

All definitions are:
- Immutable data structures (no side effects)
- Fully serializable
- Validateable at load time
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Valid field types for InputConfig/OutputConfig
VALID_FIELD_TYPES = {"string", "integer", "number", "boolean", "array", "object"}


@dataclass
class FieldDefinition:
    """
    Definition of a single typed field for input/output configuration.

    Attributes:
        name: Field identifier (must be alphanumeric with underscores)
        field_type: Type of the field (string, integer, number, boolean, array, object)
        description: Human-readable description of the field
        required: Whether this field is required (default: True)
        default: Default value if field is optional
        items_type: For array fields, the type of items in the array
        properties: For object fields, nested field definitions
    """

    name: str
    field_type: str
    description: str = ""
    required: bool = True
    default: Optional[Any] = None
    items_type: Optional[str] = None
    properties: Optional[List["FieldDefinition"]] = None

    def validate(self) -> bool:
        """
        Validate the field definition.

        Returns:
            True if valid, False otherwise
        """
        # Validate name
        if not self.name or not re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*$", self.name):
            logger.error(f"Invalid field name: {self.name}")
            return False

        # Validate type
        if self.field_type not in VALID_FIELD_TYPES:
            logger.error(f"Invalid field type '{self.field_type}' for field '{self.name}'")
            return False

        # Validate array items_type
        if self.field_type == "array":
            if self.items_type and self.items_type not in VALID_FIELD_TYPES:
                logger.error(
                    f"Invalid items_type '{self.items_type}' for array field '{self.name}'"
                )
                return False

        # Validate object properties
        if self.field_type == "object" and self.properties:
            for prop in self.properties:
                if not prop.validate():
                    return False

        return True


@dataclass
class InputConfig:
    """
    Structured input definition for an agent.

    Defines the expected input parameters that an agent accepts,
    with type information and validation constraints.

    Attributes:
        fields: List of field definitions describing the input schema
    """

    fields: List[FieldDefinition] = field(default_factory=list)

    def validate(self) -> bool:
        """Validate all field definitions."""
        for f in self.fields:
            if not f.validate():
                return False
        return True


@dataclass
class OutputConfig:
    """
    Expected structured output schema for an agent.

    Defines the expected output format that an agent should produce,
    enabling validation and type checking of agent responses.

    Attributes:
        fields: List of field definitions describing the output schema
    """

    fields: List[FieldDefinition] = field(default_factory=list)

    def validate(self) -> bool:
        """Validate all field definitions."""
        for f in self.fields:
            if not f.validate():
                return False
        return True


@dataclass
class PromptConfig:
    """
    Prompt configuration for an agent.

    Defines the system prompt and optional user prompt template
    that guide the agent's behavior.

    Attributes:
        system_prompt: The system prompt that defines agent behavior
        user_prompt_template: Optional template for formatting user prompts
    """

    system_prompt: str
    user_prompt_template: Optional[str] = None

    def validate(self) -> bool:
        """Validate prompt configuration."""
        if not self.system_prompt or not self.system_prompt.strip():
            logger.error("PromptConfig requires a non-empty system_prompt")
            return False
        return True


@dataclass
class AgentModelConfig:
    """
    Model preferences for an agent.

    Specifies the preferred model and fallback options for agent execution.

    Attributes:
        model_name: Primary model name or alias to use
        fallback_models: Ordered list of fallback model names
    """

    model_name: str
    fallback_models: List[str] = field(default_factory=list)

    def validate(self) -> bool:
        """Validate model configuration."""
        if not self.model_name or not self.model_name.strip():
            logger.error("AgentModelConfig requires a non-empty model_name")
            return False
        return True


# Alias for backward compatibility with the interface spec
ModelConfig = AgentModelConfig


@dataclass
class RunConfig:
    """
    Execution limits and constraints for an agent.

    Defines boundaries for agent execution to prevent runaway tasks
    and ensure resource management.

    Attributes:
        max_turns: Maximum conversation turns allowed (default: 10)
        max_execution_time: Maximum execution time in seconds (default: 300)
        retry_limit: Maximum retry attempts on failure (default: 3)
    """

    max_turns: int = 10
    max_execution_time: int = 300
    retry_limit: int = 3

    def validate(self) -> bool:
        """Validate run configuration."""
        if self.max_turns <= 0:
            logger.error(f"max_turns must be positive, got {self.max_turns}")
            return False
        if self.max_execution_time <= 0:
            logger.error(f"max_execution_time must be positive, got {self.max_execution_time}")
            return False
        if self.retry_limit < 0:
            logger.error(f"retry_limit must be non-negative, got {self.retry_limit}")
            return False
        return True


@dataclass
class ToolConfig:
    """
    Tool access configuration for an agent.

    Defines which tools an agent is allowed to use during execution.

    Attributes:
        allowed_tools: List of tool names the agent can access
    """

    allowed_tools: List[str] = field(default_factory=list)

    def validate(self) -> bool:
        """Validate tool configuration."""
        # All tool names must be non-empty strings
        for tool in self.allowed_tools:
            if not tool or not isinstance(tool, str):
                logger.error(f"Invalid tool name in allowed_tools: {tool}")
                return False
        return True


@dataclass
class AgentDefinition:
    """
    Complete declarative agent definition.

    This is the main data structure that describes an agent without executing it.
    It combines all configuration aspects into a single, validatable contract.

    Attributes:
        name: Unique identifier for the agent
        description: Human-readable description of what the agent does
        prompt_config: Prompt templates for the agent
        model_config: Model preferences and fallbacks
        run_config: Execution limits and constraints
        tool_config: Tool access configuration
        input_config: Structured input schema (optional)
        output_config: Expected output schema (optional)
        enabled: Whether this agent is currently enabled
        version: Version string for the agent definition

    Constraints:
        - No side effects
        - Fully serializable
        - Validateable at load time
    """

    name: str
    description: str
    prompt_config: PromptConfig
    model_config: AgentModelConfig
    run_config: RunConfig = field(default_factory=RunConfig)
    tool_config: ToolConfig = field(default_factory=ToolConfig)
    input_config: Optional[InputConfig] = None
    output_config: Optional[OutputConfig] = None
    enabled: bool = True
    version: str = "1.0.0"

    def validate(self) -> bool:
        """
        Validate the complete agent definition.

        Returns:
            True if all validations pass, False otherwise
        """
        # Validate name
        if not self.name or not re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*$", self.name):
            logger.error(f"Invalid agent name: {self.name}")
            return False

        # Validate description
        if not self.description or not self.description.strip():
            logger.error(f"Agent {self.name} requires a non-empty description")
            return False

        # Validate prompt_config
        if not self.prompt_config.validate():
            logger.error(f"Agent {self.name} has invalid prompt_config")
            return False

        # Validate model_config
        if not self.model_config.validate():
            logger.error(f"Agent {self.name} has invalid model_config")
            return False

        # Validate run_config
        if not self.run_config.validate():
            logger.error(f"Agent {self.name} has invalid run_config")
            return False

        # Validate tool_config
        if not self.tool_config.validate():
            logger.error(f"Agent {self.name} has invalid tool_config")
            return False

        # Validate input_config if present
        if self.input_config and not self.input_config.validate():
            logger.error(f"Agent {self.name} has invalid input_config")
            return False

        # Validate output_config if present
        if self.output_config and not self.output_config.validate():
            logger.error(f"Agent {self.name} has invalid output_config")
            return False

        # Validate version format (semver-like)
        if not re.match(r"^\d+\.\d+\.\d+$", self.version):
            logger.error(f"Invalid version format for agent {self.name}: {self.version}")
            return False

        return True

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert the agent definition to a dictionary for serialization.

        Returns:
            Dictionary representation of the agent definition
        """
        result: Dict[str, Any] = {
            "name": self.name,
            "description": self.description,
            "prompt_config": {
                "system_prompt": self.prompt_config.system_prompt,
                "user_prompt_template": self.prompt_config.user_prompt_template,
            },
            "model_config": {
                "model_name": self.model_config.model_name,
                "fallback_models": self.model_config.fallback_models,
            },
            "run_config": {
                "max_turns": self.run_config.max_turns,
                "max_execution_time": self.run_config.max_execution_time,
                "retry_limit": self.run_config.retry_limit,
            },
            "tool_config": {
                "allowed_tools": self.tool_config.allowed_tools,
            },
            "enabled": self.enabled,
            "version": self.version,
        }

        if self.input_config:
            result["input_config"] = {
                "fields": [self._field_to_dict(f) for f in self.input_config.fields]
            }

        if self.output_config:
            result["output_config"] = {
                "fields": [self._field_to_dict(f) for f in self.output_config.fields]
            }

        return result

    def _field_to_dict(self, f: FieldDefinition) -> Dict[str, Any]:
        """Convert a FieldDefinition to dictionary."""
        result: Dict[str, Any] = {
            "name": f.name,
            "field_type": f.field_type,
            "description": f.description,
            "required": f.required,
        }
        if f.default is not None:
            result["default"] = f.default
        if f.items_type:
            result["items_type"] = f.items_type
        if f.properties:
            result["properties"] = [self._field_to_dict(p) for p in f.properties]
        return result

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AgentDefinition":
        """
        Create an AgentDefinition from a dictionary.

        Args:
            data: Dictionary representation of the agent definition

        Returns:
            AgentDefinition instance
        """
        prompt_data = data.get("prompt_config", {})
        prompt_config = PromptConfig(
            system_prompt=prompt_data.get("system_prompt", ""),
            user_prompt_template=prompt_data.get("user_prompt_template"),
        )

        model_data = data.get("model_config", {})
        model_config = AgentModelConfig(
            model_name=model_data.get("model_name", ""),
            fallback_models=model_data.get("fallback_models", []),
        )

        run_data = data.get("run_config", {})
        run_config = RunConfig(
            max_turns=run_data.get("max_turns", 10),
            max_execution_time=run_data.get("max_execution_time", 300),
            retry_limit=run_data.get("retry_limit", 3),
        )

        tool_data = data.get("tool_config", {})
        tool_config = ToolConfig(
            allowed_tools=tool_data.get("allowed_tools", []),
        )

        input_config = None
        if "input_config" in data:
            input_fields = [cls._field_from_dict(f) for f in data["input_config"].get("fields", [])]
            input_config = InputConfig(fields=input_fields)

        output_config = None
        if "output_config" in data:
            output_fields = [
                cls._field_from_dict(f) for f in data["output_config"].get("fields", [])
            ]
            output_config = OutputConfig(fields=output_fields)

        return cls(
            name=data.get("name", ""),
            description=data.get("description", ""),
            prompt_config=prompt_config,
            model_config=model_config,
            run_config=run_config,
            tool_config=tool_config,
            input_config=input_config,
            output_config=output_config,
            enabled=data.get("enabled", True),
            version=data.get("version", "1.0.0"),
        )

    @classmethod
    def _field_from_dict(cls, data: Dict[str, Any]) -> FieldDefinition:
        """Create a FieldDefinition from dictionary."""
        properties = None
        if "properties" in data:
            properties = [cls._field_from_dict(p) for p in data["properties"]]

        return FieldDefinition(
            name=data.get("name", ""),
            field_type=data.get("field_type", "string"),
            description=data.get("description", ""),
            required=data.get("required", True),
            default=data.get("default"),
            items_type=data.get("items_type"),
            properties=properties,
        )

    def to_tool_description(self) -> str:
        """
        Generate a concise, LLM-friendly tool description.

        Returns a structured description suitable for tool calling,
        including agent purpose, inputs, and outputs.

        Returns:
            Formatted tool description string
        """
        lines = [f"**{self.name}**: {self.description}"]

        # Input summary
        if self.input_config and self.input_config.fields:
            required_fields = [f for f in self.input_config.fields if f.required]
            optional_fields = [f for f in self.input_config.fields if not f.required]

            if required_fields:
                req_names = ", ".join(f"`{f.name}`" for f in required_fields)
                lines.append(f"- **Required**: {req_names}")

            if optional_fields:
                opt_names = ", ".join(f"`{f.name}`" for f in optional_fields)
                lines.append(f"- **Optional**: {opt_names}")
        else:
            lines.append("- **Inputs**: None")

        # Output summary
        if self.output_config and self.output_config.fields:
            out_names = ", ".join(f"`{f.name}`" for f in self.output_config.fields)
            lines.append(f"- **Returns**: {out_names}")

        return "\n".join(lines)

    def to_system_prompt_snippet(self) -> str:
        """
        Generate a system prompt snippet for this agent.

        Returns a concise snippet that can be included in system prompts
        to describe this agent's capabilities for A2A delegation.

        Returns:
            System prompt snippet string
        """
        parts = [f"Agent: {self.name}"]
        parts.append(f"Purpose: {self.description}")

        # Input fields with types
        if self.input_config and self.input_config.fields:
            input_parts = []
            for f in self.input_config.fields:
                req_marker = "*" if f.required else ""
                input_parts.append(f"{f.name}{req_marker}: {f.field_type}")
            parts.append(f"Inputs: {', '.join(input_parts)}")

        # Output fields
        if self.output_config and self.output_config.fields:
            output_parts = [f"{f.name}: {f.field_type}" for f in self.output_config.fields]
            parts.append(f"Outputs: {', '.join(output_parts)}")

        # Tools available
        if self.tool_config.allowed_tools:
            parts.append(f"Tools: {', '.join(self.tool_config.allowed_tools)}")

        return "\n".join(parts)

    def to_invocation_summary(self) -> Dict[str, Any]:
        """
        Generate a structured summary for agent invocation.

        Returns a dictionary with essential invocation metadata,
        suitable for LLM context or logging.

        Returns:
            Dictionary with agent invocation summary
        """
        summary: Dict[str, Any] = {
            "name": self.name,
            "description": self.description,
            "model": self.model_config.model_name,
            "version": self.version,
        }

        if self.input_config and self.input_config.fields:
            summary["inputs"] = {
                "required": [f.name for f in self.input_config.fields if f.required],
                "optional": [f.name for f in self.input_config.fields if not f.required],
            }

        if self.output_config and self.output_config.fields:
            summary["outputs"] = [f.name for f in self.output_config.fields]

        if self.tool_config.allowed_tools:
            summary["tools"] = self.tool_config.allowed_tools

        return summary
