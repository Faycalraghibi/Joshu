# Command Processing

The Command Processing system provides standardized command handlers and action return types for CLI operations.

## Overview

This system enables:

- **Standardized action returns** for consistent command handling
- **Project initialization** via GEMINI.md generation
- **State restoration** from checkpoints with Git integration
- **Extension management** listing and configuration

## Quick Start

```python
from joshu.commands import (
    perform_init,
    perform_restore,
    list_extensions,
    RestoreToolCallData,
)
from pathlib import Path

# Initialize project
result = perform_init(Path("./my-project"))

# List extensions
result = list_extensions({"extensions": ["mcp-server", "git-tools"]})
```

## Command Action Returns

All commands return standardized action types:

### CommandActionType

```python
class CommandActionType(Enum):
    TOOL_CALL = "tool_call"          # Schedule tool execution
    MESSAGE = "message"               # Display to user
    LOAD_HISTORY = "load_history"     # Restore conversation
    SUBMIT_PROMPT = "submit_prompt"   # Send to LLM
    ERROR = "error"                   # Report error
    SUCCESS = "success"               # Report success
    NO_OP = "no_op"                   # No action needed
```

### ToolActionReturn

Schedule a tool call:

```python
from joshu.commands import ToolActionReturn

action = ToolActionReturn(
    tool_name="write_file",
    tool_arguments={"path": "file.txt", "content": "..."},
    requires_approval=True,
)
```

### MessageActionReturn

Display message to user:

```python
from joshu.commands import MessageActionReturn

action = MessageActionReturn(
    message="Operation completed successfully",
    message_type="success",  # info, warning, error, success
)
```

### LoadHistoryActionReturn

Load conversation history:

```python
from joshu.commands import LoadHistoryActionReturn

action = LoadHistoryActionReturn(
    history=[{"role": "user", "content": "Hello"}],
    client_history=[],
    replace_existing=True,
)
```

### SubmitPromptActionReturn

Submit prompt to LLM:

```python
from joshu.commands import SubmitPromptActionReturn

action = SubmitPromptActionReturn(
    prompt="Analyze this codebase and generate documentation",
    system_instruction="You are a documentation expert",
    include_context=True,
)
```

### ErrorActionReturn

Report an error:

```python
from joshu.commands import ErrorActionReturn

action = ErrorActionReturn(
    error_message="Failed to connect to Git repository",
    error_code="GIT_CONNECTION_ERROR",
    recoverable=True,
)
```

## Project Initialization

### perform_init

Creates GEMINI.md project descriptor:

```python
from joshu.commands import perform_init
from pathlib import Path

# If GEMINI.md exists
result = perform_init(Path("./existing-project"))
# Returns: NoOpActionReturn

# If GEMINI.md doesn't exist
result = perform_init(Path("./new-project"))
# Returns: SubmitPromptActionReturn with AI generation prompt
```

The generated prompt instructs an AI agent to:
1. Analyze directory structure
2. Identify project type and technologies
3. Generate appropriate GEMINI.md content

### Override Existence Check

```python
# Force generation even if file exists
result = perform_init(project_dir, does_gemini_md_exist=False)
```

## State Restoration

### perform_restore

Restores agent state from checkpoint (generator-based):

```python
from joshu.commands import perform_restore, RestoreToolCallData, GitService

# Prepare restoration data
data = RestoreToolCallData(
    checkpoint_tag="before_refactor",
    history=[
        {"role": "user", "content": "Refactor the code"},
        {"role": "assistant", "content": "I'll help you..."},
    ],
    client_history=[],
    commit_hash="abc123",  # Optional Git revision
)

# Execute restoration (yields actions)
for action in perform_restore(data, git_service):
    if isinstance(action, MessageActionReturn):
        print(action.message)
    elif isinstance(action, LoadHistoryActionReturn):
        session.load_history(action.history)
    elif isinstance(action, ErrorActionReturn):
        handle_error(action.error_message)
```

### RestoreToolCallData

```python
@dataclass
class RestoreToolCallData:
    checkpoint_tag: str                    # Checkpoint identifier
    history: List[Dict[str, Any]]          # Conversation history
    client_history: List[Dict[str, Any]]   # Client-specific data
    commit_hash: Optional[str] = None      # Git revision to restore
```

### GitService

Interface for Git operations:

```python
from joshu.commands import GitService

git = GitService(project_root=Path("./my-project"))

# Check current state
current = git.get_current_commit()
has_changes = git.has_uncommitted_changes()

# Checkout specific commit
success = git.checkout_commit("abc123")
```

## Extension Management

### list_extensions

Lists configured extensions:

```python
from joshu.commands import list_extensions

config = {
    "extensions": ["mcp-server", "file-browser", "git-tools"]
}

result = list_extensions(config)
# Returns: MessageActionReturn with formatted list
```

## Processing Actions

Handle returned actions in your application:

```python
from joshu.commands import CommandActionType

def process_action(action):
    match action.action_type:
        case CommandActionType.MESSAGE:
            display_message(action.message, action.message_type)

        case CommandActionType.TOOL_CALL:
            if action.requires_approval:
                if user_approves():
                    execute_tool(action.tool_name, action.tool_arguments)
            else:
                execute_tool(action.tool_name, action.tool_arguments)

        case CommandActionType.LOAD_HISTORY:
            session.load_history(action.history)

        case CommandActionType.SUBMIT_PROMPT:
            response = llm.generate(
                action.prompt,
                system=action.system_instruction,
            )

        case CommandActionType.ERROR:
            log_error(action.error_code, action.error_message)
            if not action.recoverable:
                raise CommandError(action.error_message)

        case CommandActionType.NO_OP:
            pass  # Nothing to do
```

## Best Practices

1. **Check action types**: Always handle all possible return types
2. **Use generators**: `perform_restore` yields multiple actions
3. **Handle errors**: Check for `recoverable` flag
4. **Preserve metadata**: Action metadata contains useful context
5. **Initialize early**: Run `perform_init` on new projects

## A2A Server Integration

The Command Processing system integrates with the [A2A Server](a2a-server.md) for HTTP-based command execution:

- Commands are registered via `CommandRegistry` for CLI-to-server bridging
- The `/executeCommand` endpoint streams command results via SSE
- The `/listCommands` endpoint exposes available commands to external clients

See the A2A Server documentation for HTTP API details.

## See Also

- [A2A Server](a2a-server.md) - HTTP/SSE server integration
- [CLI Reference](cli-reference.md) - Command-line interface
- [Chat and Scheduling](chat-and-scheduling.md) - Session management
- [Configuration](configuration.md) - System settings
