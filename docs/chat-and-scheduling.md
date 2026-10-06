# Chat Session and Tool Scheduling

The Chat Session and Tool Scheduling modules provide infrastructure for managing conversational interactions and tool execution during agent processing.

## Overview

This system includes:

- **Chat Session Management** - History, checkpointing, and lifecycle
- **Tool Scheduler** - Approval modes, queuing, and execution control
- **Hook System** - Lifecycle hooks for pre/post processing
- **Credential Storage** - API key and OAuth management

## Chat Sessions

### ChatSession

Manages a single conversation session:

```python
from joshu.core.chat_session import (
    ChatSession,
    ChatSessionConfig,
    ChatMessage,
)

# Create session
config = ChatSessionConfig(
    model="gpt-4o",
    system_prompt="You are a helpful assistant.",
    temperature=0.7,
)
session = ChatSession(config)

# Start session
session.start()

# Add messages
session.add_user_message("Hello!")
response = session.add_assistant_message("Hi there!")

# Get messages for API
messages = session.get_messages_for_api()
```

### ChatMessage

Messages with role-based factory methods:

```python
# Create messages
msg = ChatMessage.system("You are a coder")
msg = ChatMessage.user("Write Python code")
msg = ChatMessage.assistant("Here's the code...")
msg = ChatMessage.tool("Result", tool_call_id="xyz", name="run_code")

# Convert to API format
data = msg.to_dict()
```

### Session Checkpointing

Save and restore session state:

```python
# Create checkpoint
checkpoint = session.create_checkpoint("before_refactor")

# Make changes
session.add_user_message("Refactor the code")
session.add_assistant_message("Done!")

# Restore if needed
session.restore_checkpoint("before_refactor")

# Reset completely
session.reset()
```

### ChatHistory

Manages message history with trimming:

```python
from joshu.core.chat_session import ChatHistory

history = ChatHistory(max_messages=100)

# Add messages
history.add(ChatMessage.user("Hello"))
history.add(ChatMessage.assistant("Hi"))

# Get for API (curated or full)
messages = history.get_for_api(curated=False)

# Get last N
recent = history.get_last_n(5)
```

## Tool Scheduler

### CoreToolScheduler

Manages tool call lifecycle with approval:

```python
from joshu.core.tool_scheduler import (
    CoreToolScheduler,
    ToolSchedulerConfig,
    ApprovalMode,
)

# Configure scheduler
config = ToolSchedulerConfig(
    approval_mode=ApprovalMode.SAFE_ONLY,
    safe_tools=["read_file", "list_dir", "web_search"],
    max_output_display=2000,
)
scheduler = CoreToolScheduler(config)

# Schedule a tool call
call = scheduler.schedule(
    tool_name="execute_code",
    arguments={"code": "print('hello')"},
)

# Check if approval needed
if call.requires_approval:
    # Wait for user approval
    scheduler.approve(call.call_id)
```

### ApprovalMode

```python
class ApprovalMode(Enum):
    AUTO_APPROVE = "auto_approve"  # Approve all
    MANUAL = "manual"              # Require confirmation
    SAFE_ONLY = "safe_only"        # Auto-approve safe tools
    NEVER = "never"                # Reject all
```

### ScheduledToolCall

```python
@dataclass
class ScheduledToolCall:
    call_id: str
    tool_name: str
    arguments: Dict[str, Any]
    status: ToolCallStatus
    requires_approval: bool
    result: Optional[str]
    error: Optional[str]
```

### Output Truncation

```python
# Truncate long output
output = scheduler.truncate_output(
    output=very_long_string,
    call_id=call.call_id,  # Saves full output to temp file
)
```

## Hook System

### HookRegistry

Register lifecycle hooks:

```python
from joshu.core.hooks import (
    HookRegistry,
    HookPhase,
    HookContext,
    get_hook_registry,
)

registry = get_hook_registry()

# Register with decorator
@registry.hook(HookPhase.BEFORE_MODEL, priority=10)
def log_request(ctx: HookContext) -> HookContext:
    print(f"Request: {ctx.data}")
    return ctx

# Or register directly
registry.register(
    name="validate_input",
    phase=HookPhase.BEFORE_MODEL,
    handler=validate_handler,
    priority=5,
)
```

### HookPhase

Available lifecycle phases:

```python
class HookPhase(Enum):
    BEFORE_MODEL = "before_model"
    AFTER_MODEL = "after_model"
    BEFORE_TOOL_SELECTION = "before_tool_selection"
    AFTER_TOOL_SELECTION = "after_tool_selection"
    BEFORE_TOOL_EXECUTION = "before_tool_execution"
    AFTER_TOOL_EXECUTION = "after_tool_execution"
    BEFORE_AGENT = "before_agent"
    AFTER_AGENT = "after_agent"
    ON_ERROR = "on_error"
    ON_STREAM_CHUNK = "on_stream_chunk"
```

### HookContext

Context passed to hooks:

```python
@dataclass
class HookContext:
    phase: HookPhase
    data: Any                  # Phase-specific data
    session_id: Optional[str]
    turn_number: int
    metadata: Dict[str, Any]
    should_continue: bool      # Set False to abort
    modified_data: Optional[Any]

    def modify(self, new_data: Any) -> None:
        """Set modified data."""
        self.modified_data = new_data

    def abort(self, reason: str = "") -> None:
        """Abort processing."""
        self.should_continue = False
```

### Firing Hooks

```python
# Fire hooks for a phase
context = registry.fire(
    phase=HookPhase.BEFORE_MODEL,
    data=request_data,
    session_id=session.session_id,
    turn_number=5,
)

# Check if aborted
if not context.should_continue:
    return context.metadata.get("abort_reason")

# Use potentially modified data
data = context.get_effective_data()
```

## Credential Storage

### Memory Storage

For testing:

```python
from joshu.core.credentials import (
    MemoryCredentialStorage,
    OAuthCredentials,
    StoredCredential,
    CredentialType,
)

storage = MemoryCredentialStorage()

# Store API key
creds = OAuthCredentials.from_api_key("sk-...")
stored = StoredCredential(
    credential_type=CredentialType.API_KEY,
    credentials=creds,
    service_name="openai",
)
storage.save(stored)

# Load
loaded = storage.load("openai")
```

### Hybrid Storage

Tries keychain first, falls back to file:

```python
from joshu.core.credentials import (
    HybridCredentialStorage,
    HybridStorageConfig,
)

config = HybridStorageConfig(
    prefer_keychain=True,
    file_path="~/.joshu/credentials.json",
    encrypt_file=True,
)
storage = HybridCredentialStorage(config)
```

## Best Practices

1. **Session per conversation**: Create new session for each conversation
2. **Checkpoint before risky ops**: Save before major changes
3. **Use SAFE_ONLY mode**: Auto-approve only safe tools
4. **Register hooks early**: Set up hooks before starting sessions
5. **Truncate outputs**: Limit display size for large outputs

## See Also

- [Agent Tools](agent.md#tools) - Tool registration and execution
- [Configuration](configuration.md) - System settings
