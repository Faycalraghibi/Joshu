"""
Declarative agent definitions (YAML/JSON).

Sub-agents for the `task` tool can be written in this format as well as in
Markdown (see joshu.core.subagents, which loads them with load_agents_from_path).

- definitions: dataclasses for an agent's prompt, model, tools and limits
- loader: JSON / YAML loaders
- exceptions: errors raised while loading
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
