# Context System

## Overview

The Context System maintains conversation state, memory, and system information across Joshu sessions. It provides relevant context to LLMs for better command translation and completion suggestions.

## Components

### 1. Context Provider

The main interface for managing context:

- **Conversation History**: Recent user/assistant messages
- **Memory Store**: Persistent key-value storage
- **System Information**: OS, shell, environment details
- **Session Management**: Isolate context by session

### 2. Storage Backend

Context is persisted using storage backends:

- **JsonFileStorage**: Default file-based storage
- **Session Isolation**: Separate contexts per session
- **Query Interface**: Flexible data retrieval

## Using the Context System

### Basic Operations

```python
from joshu.core.context_provider import ContextProvider

# Create context provider
context = ContextProvider()

# Add to conversation history
context.add_to_history("user", "show disk usage")
context.add_to_history("assistant", "Executed: df -h")

# Set memory values
context.set_memory("user_preference", "verbose output")
context.set_memory("last_command", "df -h")

# Get memory values
preference = context.get_memory("user_preference")  # "verbose output"
unknown = context.get_memory("nonexistent"# None
```

### Getting Relevant Context

The system automatically builds relevant context for queries:

```python
# Get context relevant to a query
query = "show Python files"
context_messages = context.get_relevant_context(query)

# Returns list of messages including:
# - System information
# - Recent conversation history
# -Related memory entries
```

### Context Summary

```python
# Get overview of current context
summary = context.get_context_summary()

print(summary)
# {
#     "history_length": 10,
#     "memory_entries": 5,
#     "system_info": "Windows 11",
#     "recent_history": [...]
# }
```

### Clearing Context

```python
# Clear all context (history + memory)
context.clear_context()

# History and memory are now empty
assert len(context.conversation_context.messages) == 0
assert len(context.memory_store.kv) == 0
```

## Configuration

### History Limits

Control how much history is kept in memory:

```python
# Keep only last 50 messages
context = ContextProvider(max_history=50)

# Add more messages than limit
for i in range(100):
    context.add_to_history("user", f"Message {i}")

# Only last 50 are kept
assert len(context.conversation_context.messages) == 50
```

### Memory Limits

```python
# Limit memory entries
context = ContextProvider(max_memory_entries=1000)
```

### Custom Storage

```python
from pathlib import Path
from joshu.core.storage import JsonFileStorage

# Use custom storage location
storage = JsonFileStorage(Path("~/.my_app/context.json").expanduser())
context = ContextProvider(storage_backend=storage)
```

## Session Management

### Sessions

Each context provider operates within a session:

```python
# Get current session ID
session_id = context.session_id

# List all sessions
sessions = context.list_sessions()
for session in sessions:
    print(f"Session {session['id']}: {session['created_at']}")

# End current session (clears and creates new)
context.end_session()
```

### Session Isolation

Sessions keep context separate:

```python
# Session 1
context1 = ContextProvider()
context1.add_to_history("user", "message in session 1")

# Session 2 (new instance = new session)
context2 = ContextProvider()
# Does not see session 1 history
assert len(context2.conversation_context.messages) == 0

# But can query storage for all sessions
from joshu.core.storage import QueryFilter, EntryType
filter = QueryFilter(entry_type=EntryType.CONVERSATION)
all_conversations = context2.storage_backend.query_entries(filter)
```

## Storage System

### Entry Types

Context data is stored in different types:

```python
from joshu.core.storage import EntryType

# Available types:
EntryType.CONVERSATION  # Chat messages
EntryType.MEMORY        # Key-value pairs
EntryType.SYSTEM_INFO   # System details
EntryType.SESSION       # Session metadata
```

### Querying Storage

```python
from joshu.core.storage import QueryFilter, EntryType

# Query conversations
filter = QueryFilter(
    entry_type=EntryType.CONVERSATION,
    role="user",  # Only user messages
    limit=10      # Last 10 messages
)
messages = context.storage_backend.query_entries(filter)

# Query memory
filter = QueryFilter(entry_type=EntryType.MEMORY)
memory_entries = context.storage_backend.query_entries(filter)
```

### Persistence

Context is automatically persisted to storage:

```python
# Create provider with storage
context1 = ContextProvider(storage_backend=storage)
context1.set_memory("key", "value")

# New provider with same storage loads memory
context2 = ContextProvider(storage_backend=storage)
assert context2.get_memory("key") == "value"
```

## Integration with Commands

### Automatic Context Usage

Commands automatically receive context:

```bash
# Context is used for:
# - Understanding command intent
# - Providing relevant history
# - Remembering user preferences
joshu "show me those Python files again"
# ^ Context remembers previous Python file queries
```

### Interactive Mode

In interactive mode, context persists across commands:

```bash
joshu interactive

joshu> show disk usage
# Context: user asked about disk usage

joshu> and memory usage too
# Context: remembers we're discussing system resources
```

### Memory Commands

Set and query memory in interactive mode:

```bash
joshu> /memory set project_dir /home/user/myproject
joshu> /memory get project_dir
joshu> /memory list
```

## Best Practices

1. **Clear Context Periodically**: Prevents context from growing too large
2. **Use Memory for Preferences**: Store user preferences in memory
3. **Session Per Task**: Start new session for unrelated tasks
4. **Monitor Context Size**: Check history length if performance degrades

## Advanced Usage

### Custom Context Providers

Extend `ContextProvider` for custom behavior:

```python
class CustomContextProvider(ContextProvider):
    def get_relevant_context(self, query):
        # Custom logic to filter context
        context = super().get_relevant_context(query)
        # Add domain-specific context
        return context + self._get_domain_context(query)
```

### Direct Storage Access

Access storage directly for advanced queries:

```python
# Get all user messages from last 24 hours
import time
from joshu.core.storage import QueryFilter, EntryType

cutoff_time = time.time() - (24 * 60 * 60)
filter = QueryFilter(
    entry_type=EntryType.CONVERSATION,
    role="user"
)
all_messages = context.storage_backend.query_entries(filter)
recent = [m for m in all_messages if m.timestamp > cutoff_time]
```

## Troubleshooting

### Context Not Persisting

- Verify storage path is writable
- Check storage backend is set
- Ensure `clear_context()` isn't being called unexpectedly

### Memory Leaks

- Set appropriate `max_history` and `max_memory_entries`
- Clear old sessions periodically
- Monitor storage file size

### Session Conflicts

- Use separate storage paths for concurrent Joshu instances
- End sessions properly when done

## Related Documentation

- [Storage System](testing-guide.md#storage-system) - Storage implementation details
- [Interactive Mode](interactive-mode.md) - Using context in interactive mode
- [Configuration](configuration.md) - Context system settings
