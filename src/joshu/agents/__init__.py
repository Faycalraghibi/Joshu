"""
Agent Definition and Registration System for Joshu.

This package provides a declarative agent definition and registration system
that allows AI agents to be discovered, validated, configured, and exposed
as callable tools for agent-to-agent delegation.

Key components:
- definitions: Core dataclasses for agent configuration
- schema_converter: InputConfig to JSON Schema conversion
- registry: Central registry for agent definitions
- tool_wrapper: SubagentToolWrapper for agent-as-tool exposure
- exceptions: Custom exception classes
"""

from joshu.agents.definitions import (
    AgentDefinition,
    FieldDefinition,
    InputConfig,
    ModelConfig,
    OutputConfig,
    PromptConfig,
    RunConfig,
    ToolConfig,
)
from joshu.agents.delegate_tool import (
    DelegateToAgentTool,
    DelegationRequest,
    create_delegate_tool,
)
from joshu.agents.exceptions import (
    AgentError,
    AgentNotFoundError,
    AgentRegistrationError,
    AgentValidationError,
    SchemaConversionError,
)
from joshu.agents.loader import (
    AgentLoader,
    CompositeAgentLoader,
    JsonAgentLoader,
    YamlAgentLoader,
    load_agents_from_path,
)
from joshu.agents.registry import AgentRegistry, get_agent_registry
from joshu.agents.schema_converter import input_config_to_json_schema
from joshu.agents.tool_wrapper import SubagentToolWrapper

__all__ = [
    # Definitions
    "AgentDefinition",
    "FieldDefinition",
    "InputConfig",
    "OutputConfig",
    "PromptConfig",
    "ModelConfig",
    "RunConfig",
    "ToolConfig",
    # Registry
    "AgentRegistry",
    "get_agent_registry",
    # Tool Wrapper
    "SubagentToolWrapper",
    # Delegation
    "DelegateToAgentTool",
    "DelegationRequest",
    "create_delegate_tool",
    # Schema Conversion
    "input_config_to_json_schema",
    # Loaders
    "AgentLoader",
    "JsonAgentLoader",
    "YamlAgentLoader",
    "CompositeAgentLoader",
    "load_agents_from_path",
    # Exceptions
    "AgentError",
    "AgentValidationError",
    "AgentRegistrationError",
    "AgentNotFoundError",
    "SchemaConversionError",
]
