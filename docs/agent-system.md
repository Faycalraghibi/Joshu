# Agent Definition and Registration System

The Agent Definition and Registration System provides a declarative, execution-agnostic framework for defining, registering, and managing AI agents within Joshu. This system is the foundation for agent-to-agent (A2A) communication and task delegation.

## Overview

This system enables:

- **Declarative agent definitions** via Python dataclasses
- **Centralized registration** via `AgentRegistry` singleton
- **Subagent delegation** via `DelegateToAgentTool`
- **File-based discovery** via JSON/YAML loaders
- **LLM-friendly descriptions** for agent-to-agent communication
- **Schema conversion** from Python types to JSON Schema

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    AgentRegistry (Singleton)                 │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐         │
│  │ Agent Def 1 │  │ Agent Def 2 │  │ Agent Def N │         │
│  └─────────────┘  └─────────────┘  └─────────────┘         │
├─────────────────────────────────────────────────────────────┤
│  Model Aliases │ Config Overrides │ Validation Rules        │
└─────────────────────────────────────────────────────────────┘
         │                    │                    │
         ▼                    ▼                    ▼
┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
│ JsonAgentLoader │  │ YamlAgentLoader │  │ DelegateToAgent │
│                 │  │                 │  │     Tool        │
└─────────────────┘  └─────────────────┘  └─────────────────┘
```

## Quick Start

```python
from joshu.agents import (
    AgentDefinition,
    AgentRegistry,
    InputConfig,
    OutputConfig,
    PromptConfig,
    FieldDefinition,
    ModelConfig,
)

# Define an agent with full configuration
agent = AgentDefinition(
    name="research_agent",
    description="Researches topics and provides comprehensive summaries",
    input_config=InputConfig(fields=[
        FieldDefinition(
            name="topic",
            field_type="string",
            required=True,
            description="The topic to research",
        ),
        FieldDefinition(
            name="depth",
            field_type="string",
            required=False,
            default="medium",
            description="Research depth: shallow, medium, or deep",
        ),
        FieldDefinition(
            name="max_sources",
            field_type="integer",
            required=False,
            default=5,
            description="Maximum number of sources to include",
        ),
    ]),
    output_config=OutputConfig(
        format="markdown",
        schema={"type": "object", "properties": {"summary": {"type": "string"}}},
    ),
    prompt_config=PromptConfig(
        system_prompt="You are a research assistant. Analyze topics thoroughly.",
        user_prompt_template="Research the following topic: {topic}",
    ),
    model_config=ModelConfig(
        model_name="gpt-4o",
        temperature=0.3,
        max_tokens=4000,
    ),
)

# Register the agent
registry = AgentRegistry()
registry.register(agent)
```

## Core Components

### AgentDefinition

The main dataclass representing an agent's complete specification:

```python
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any

@dataclass
class AgentDefinition:
    # Required fields
    name: str                         # Unique identifier
    description: str                  # Human-readable description

    # Optional configuration
    input_config: Optional[InputConfig] = None   # Input parameters
    output_config: Optional[OutputConfig] = None # Output schema
    prompt_config: Optional[PromptConfig] = None # System/user prompts
    model_config: Optional[ModelConfig] = None   # Model settings
    run_config: Optional[RunConfig] = None       # Execution settings
    tools: List[ToolConfig] = field(default_factory=list)  # Available tools

    # State
    enabled: bool = True              # Whether agent is active
    version: str = "1.0.0"            # Agent version
    tags: List[str] = field(default_factory=list)  # Categorization
    metadata: Dict[str, Any] = field(default_factory=dict)  # Custom data
```

**Key Methods:**

```python
# Validate the agent definition
agent.validate()  # Raises AgentValidationError if invalid

# Serialize to dictionary
data = agent.to_dict()

# Create from dictionary
agent = AgentDefinition.from_dict(data)

# Generate LLM-friendly descriptions
tool_desc = agent.to_tool_description()
prompt_snippet = agent.to_system_prompt_snippet()
summary = agent.to_invocation_summary()
```

### InputConfig & FieldDefinition

Define agent input parameters with automatic JSON Schema conversion:

```python
from joshu.agents import InputConfig, FieldDefinition

# Define complex input schema
input_config = InputConfig(
    fields=[
        # Required string field
        FieldDefinition(
            name="query",
            field_type="string",
            required=True,
            description="The search query",
            constraints={"minLength": 1, "maxLength": 500},
        ),

        # Optional integer with default
        FieldDefinition(
            name="limit",
            field_type="integer",
            required=False,
            default=10,
            description="Maximum results to return",
            constraints={"minimum": 1, "maximum": 100},
        ),

        # Array of strings
        FieldDefinition(
            name="filters",
            field_type="array",
            required=False,
            items_type="string",
            description="Filter criteria",
        ),

        # Nested object
        FieldDefinition(
            name="options",
            field_type="object",
            required=False,
            properties={
                "sort": {"type": "string", "enum": ["asc", "desc"]},
                "include_metadata": {"type": "boolean"},
            },
        ),
    ]
)

# Convert to JSON Schema
schema = input_config.to_json_schema()
# Result:
# {
#     "type": "object",
#     "required": ["query"],
#     "properties": {
#         "query": {"type": "string", "minLength": 1, "maxLength": 500},
#         "limit": {"type": "integer", "default": 10, "minimum": 1, "maximum": 100},
#         "filters": {"type": "array", "items": {"type": "string"}},
#         "options": {"type": "object", "properties": {...}}
#     }
# }
```

**Supported Field Types:**

| Type | Python | JSON Schema | Notes |
|------|--------|-------------|-------|
| `string` | `str` | `{"type": "string"}` | Text values |
| `integer` | `int` | `{"type": "integer"}` | Whole numbers |
| `number` | `float` | `{"type": "number"}` | Decimal numbers |
| `boolean` | `bool` | `{"type": "boolean"}` | True/False |
| `array` | `list` | `{"type": "array"}` | Use `items_type` |
| `object` | `dict` | `{"type": "object"}` | Use `properties` |

### OutputConfig

Define expected output format:

```python
from joshu.agents import OutputConfig

output_config = OutputConfig(
    format="json",  # json, markdown, text, structured
    schema={
        "type": "object",
        "required": ["status", "data"],
        "properties": {
            "status": {"type": "string", "enum": ["success", "error"]},
            "data": {"type": "object"},
            "error_message": {"type": "string"},
        }
    },
    description="Returns structured JSON with status and data",
)
```

### PromptConfig

Configure system and user prompts:

```python
from joshu.agents import PromptConfig

prompt_config = PromptConfig(
    system_prompt="""You are a specialized code review agent.

Your responsibilities:
1. Analyze code for bugs and issues
2. Suggest improvements
3. Check for security vulnerabilities
4. Ensure coding standards compliance

Always be constructive and explain your reasoning.""",

    user_prompt_template="""Review the following code:

Language: {language}
File: {filename}

```{language}
{code}
```

Focus areas: {focus_areas}""",

    examples=[
        {
            "input": {"code": "def add(a, b): return a + b"},
            "output": "The function is simple and correct..."
        }
    ],
)
```

### ModelConfig

Configure model and generation settings:

```python
from joshu.agents import ModelConfig

model_config = ModelConfig(
    model_name="gpt-4o",           # Primary model
    fallback_models=["gpt-4o-mini", "gpt-3.5-turbo"],  # Fallbacks
    temperature=0.7,               # Creativity (0.0-2.0)
    max_tokens=4000,               # Response limit
    top_p=0.9,                     # Nucleus sampling
    frequency_penalty=0.0,         # Repetition control
    presence_penalty=0.0,          # Topic diversity
    stop_sequences=["END"],        # Stop generation triggers
)
```

### RunConfig

Configure execution behavior:

```python
from joshu.agents import RunConfig

run_config = RunConfig(
    timeout_seconds=120,           # Maximum execution time
    max_retries=3,                 # Retry on failure
    retry_delay_ms=1000,           # Delay between retries
    stream_response=True,          # Enable streaming
    validate_output=True,          # Validate against schema
    log_level="INFO",              # Logging verbosity
)
```

## AgentRegistry

Singleton registry for managing agents across the application:

```python
from joshu.agents import AgentRegistry, AgentNotFoundError

registry = AgentRegistry()

# Register an agent
registry.register(agent)

# Register with configuration overrides
registry.register(agent, overrides={
    "model_config": {"temperature": 0.5},
    "enabled": False,
})

# Get agent by name
try:
    agent = registry.get("research_agent")
except AgentNotFoundError:
    print("Agent not found")

# List all agents
all_agents = registry.list_agents()
enabled_only = registry.list_agents(enabled_only=True)
by_tag = registry.list_agents(tags=["research", "analysis"])

# Check if agent exists
if registry.has("research_agent"):
    print("Agent exists")

# Unregister
registry.unregister("research_agent")

# Clear all
registry.clear()
```

### Model Alias Resolution

Map logical model names to concrete models:

```python
# Set aliases
registry.set_model_alias("default", "gpt-4o")
registry.set_model_alias("fast", "gpt-4o-mini")
registry.set_model_alias("cheap", "gpt-3.5-turbo")

# Agent uses alias
agent.model_config.model_name = "default"

# Register with resolution
registry.register(agent, resolve_model_aliases=True)
# Agent now has model_name="gpt-4o"

# Also resolves fallback_models
agent.model_config.fallback_models = ["fast", "cheap"]
registry.register(agent, resolve_model_aliases=True)
# fallback_models now ["gpt-4o-mini", "gpt-3.5-turbo"]
```

## File-Based Discovery

### JSON Loading

```python
from joshu.agents import JsonAgentLoader

loader = JsonAgentLoader()

# Load from file
agents = loader.load_from_file("agents.json")

# Load from string
json_content = '''
[
    {
        "name": "summarizer",
        "description": "Summarizes text",
        "input_config": {
            "fields": [
                {"name": "text", "field_type": "string", "required": true}
            ]
        }
    }
]
'''
agents = loader.load_from_string(json_content)
```

### YAML Loading

```python
from joshu.agents import YamlAgentLoader

loader = YamlAgentLoader()

# Load from file (supports multi-document YAML)
agents = loader.load_from_file("agents.yaml")
```

**Example YAML:**

```yaml
---
name: code_reviewer
description: Reviews code for quality and issues
input_config:
  fields:
    - name: code
      field_type: string
      required: true
    - name: language
      field_type: string
      required: false
      default: python
model_config:
  model_name: gpt-4o
  temperature: 0.3
---
name: translator
description: Translates text between languages
input_config:
  fields:
    - name: text
      field_type: string
      required: true
    - name: target_language
      field_type: string
      required: true
```

### Auto-Discovery

```python
from joshu.agents import load_agents_from_path

# Automatically detects JSON or YAML based on extension
agents = load_agents_from_path("config/agents/")

# Register all discovered agents
for agent in agents:
    registry.register(agent)
```

### Registry Integration

```python
# Discover and register from path
registry.discover_from_source("config/agents/")
```

## Subagent Delegation

### DelegateToAgentTool

Enables LLM to delegate tasks to specialized subagents:

```python
from joshu.agents import DelegateToAgentTool, create_delegate_tool

# Create delegation tool
delegate_tool = DelegateToAgentTool(registry)

# Get dynamically generated schema
schema = delegate_tool.get_parameters_schema()
# Schema includes all registered agent names in enum

# Validate a delegation request
result = delegate_tool.validate_delegation(
    target_agent="research_agent",
    task_description="Research the history of AI",
    input_parameters={"topic": "artificial intelligence history", "depth": "deep"},
)

if result["success"]:
    request = result["delegation_request"]
    print(f"Delegating to: {request['target_agent']}")
else:
    print(f"Validation failed: {result['error']}")
```

### DelegationRequest

The validated request structure:

```python
@dataclass
class DelegationRequest:
    target_agent: str              # Which agent to delegate to
    task_description: str          # What to accomplish
    input_parameters: Dict         # Validated inputs
    priority: int = 0              # Execution priority
    timeout_seconds: Optional[int] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
```

### Create Tool for LLM

```python
from joshu.agents import create_delegate_tool

# Create ToolSpec for LLM
tool_spec = create_delegate_tool(registry)

# Use with tool system
from joshu.core.tool_registry import ToolRegistry
tool_registry = ToolRegistry()
tool_registry.register(tool_spec)
```

### Generate System Prompt

```python
# Get prompt snippet for available agents
prompt = delegate_tool.get_agents_for_prompt()

# Result:
"""
Available agents for delegation:
- research_agent: Researches topics and provides comprehensive summaries
  Inputs: topic (string, required), depth (string), max_sources (integer)
- code_reviewer: Reviews code for quality and issues
  Inputs: code (string, required), language (string)
"""
```

## SubagentToolWrapper

Wrap any agent as a standard tool:

```python
from joshu.agents import SubagentToolWrapper

# Create wrapper with invocation handler
wrapper = SubagentToolWrapper(
    agent=agent,
    invocation_handler=lambda agent, inputs: execute_agent(agent, inputs),
)

# Get as ToolSpec
tool_spec = wrapper.to_tool_spec()

# Or as OpenAI format
openai_tool = wrapper.to_openai_format()
# {
#     "type": "function",
#     "function": {
#         "name": "research_agent",
#         "description": "Researches topics...",
#         "parameters": {...}
#     }
# }
```

## LLM-Friendly Descriptions

### to_tool_description()

Generates concise Markdown for tool definitions:

```python
desc = agent.to_tool_description()
# """
# **research_agent**: Researches topics and provides comprehensive summaries
#
# **Inputs:**
# - `topic` (string, required): The topic to research
# - `depth` (string): Research depth
# - `max_sources` (integer): Maximum sources
# """
```

### to_system_prompt_snippet()

Generates context for system prompts:

```python
snippet = agent.to_system_prompt_snippet()
# """
# You can delegate to the `research_agent` agent.
# Purpose: Researches topics and provides comprehensive summaries
# Available tools: web_search, read_file
# Input parameters: topic, depth, max_sources
# """
```

### to_invocation_summary()

Generates structured summary for logging:

```python
summary = agent.to_invocation_summary()
# {
#     "name": "research_agent",
#     "description": "Researches topics...",
#     "model": "gpt-4o",
#     "input_fields": ["topic", "depth", "max_sources"],
#     "tools": ["web_search", "read_file"],
#     "enabled": True
# }
```

## Error Handling

```python
from joshu.agents import (
    AgentError,
    AgentValidationError,
    AgentRegistrationError,
    AgentNotFoundError,
    SchemaConversionError,
)

try:
    agent = AgentDefinition(name="", description="Invalid")
    agent.validate()
except AgentValidationError as e:
    print(f"Validation failed: {e}")

try:
    registry.register(agent)
except AgentRegistrationError as e:
    print(f"Registration failed: {e}")

try:
    agent = registry.get("nonexistent")
except AgentNotFoundError as e:
    print(f"Agent not found: {e}")
```

## Best Practices

1. **Use descriptive names**: Agent names should clearly indicate their purpose (`research_agent`, `code_reviewer`)

2. **Document inputs thoroughly**: Include descriptions, constraints, and examples for all fields

3. **Validate early**: Call `validate()` before registration to catch errors

4. **Use model aliases**: Configure aliases for easy model switching across environments

5. **Enable/disable vs delete**: Use `enabled=False` instead of unregistering for temporary deactivation

6. **Version your agents**: Use `version` field and tags for lifecycle management

7. **Leverage fallbacks**: Configure `fallback_models` for resilience

8. **Test with mocks**: Use `invocation_handler` to mock agent execution in tests

## See Also

- [Tool Calling](tool-calling.md) - Tool registration and execution
- [Model Availability](model-availability.md) - Health tracking and fallback
- [Chat & Scheduling](chat-and-scheduling.md) - Session management
- [Configuration](configuration.md) - System configuration
