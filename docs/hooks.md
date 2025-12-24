# Hooks System

The Joshu hooks system enables dynamic customization of the agentic loop by allowing external scripts to intercept, modify, and log CLI actions without altering core code.

## Overview

Hooks operate synchronously, pausing the agent loop until all relevant scripts complete. Communication between Joshu and hooks is via JSON payloads on stdin/stdout. Exit codes determine behavior:

| Exit Code | Result |
|-----------|--------|
| 0 | Success - continue execution |
| 2 | Block - abort execution |
| Other | Warning - log and continue |

## Hook Events

| Event | Description |
|-------|-------------|
| `session_start` | Beginning of a new session |
| `session_end` | End of a session |
| `before_agent` | Before agent processes a prompt |
| `after_agent` | After agent generates a response |
| `before_model` | Before sending request to LLM |
| `after_model` | After receiving response from LLM |
| `before_tool_selection` | Before LLM selects tools |
| `before_tool` | Before executing a tool |
| `after_tool` | After tool execution |
| `pre_compress` | Before context compression |
| `notification` | When a notification fires |

## Configuration

Add hooks to `~/.joshu/settings.json`:

```json
{
  "hooks": {
    "before_tool": [
      {
        "name": "security-check",
        "type": "command",
        "command": "python ~/.joshu/hooks/security.py",
        "description": "Block sensitive file writes",
        "timeout": 5000,
        "matcher": "write_file|replace"
      }
    ]
  }
}
```

### Configuration Options

| Property | Type | Description |
|----------|------|-------------|
| `name` | string | Unique identifier |
| `type` | string | Currently only `"command"` |
| `command` | string | Path to script/command |
| `description` | string | Human-readable purpose |
| `timeout` | int | Max execution time (ms) |
| `matcher` | string | Pattern to filter triggers |

## Matcher Patterns

Control which tools/events trigger a hook:

| Pattern | Matches |
|---------|---------|
| `write_file` | Exact match |
| `write_*` | Wildcard match |
| `write_file\|replace` | Multiple matches |
| `/^search.*/` | Regex match |

## Writing Hooks

### Python Example

```python
#!/usr/bin/env python
import json
import sys

def main():
    # Read payload from stdin
    payload = json.load(sys.stdin)

    event = payload["event"]
    data = payload["data"]

    # Check for sensitive operations
    if event == "before_tool":
        tool_name = data.get("tool_name")
        arguments = data.get("arguments", {})

        if tool_name == "write_file":
            path = arguments.get("path", "")
            if ".env" in path or "secret" in path.lower():
                # Block the operation
                response = {
                    "action": "block",
                    "message": "Cannot write to sensitive file"
                }
                print(json.dumps(response))
                sys.exit(2)  # Exit 2 = block

    # Allow the operation
    response = {"action": "allow"}
    print(json.dumps(response))
    sys.exit(0)

if __name__ == "__main__":
    main()
```

### Bash Example

```bash
#!/bin/bash

# Read JSON payload
payload=$(cat)

# Parse with jq
event=$(echo "$payload" | jq -r '.event')
tool_name=$(echo "$payload" | jq -r '.data.tool_name // ""')

# Log tool usage
echo "[$(date)] $event: $tool_name" >> ~/.joshu/hooks.log

# Allow execution
echo '{"action": "allow"}'
exit 0
```

## Payload Structure

### Input (stdin)

```json
{
  "event": "before_tool",
  "session_id": "abc123",
  "timestamp": "2024-01-15T10:30:00Z",
  "data": {
    "tool_name": "write_file",
    "arguments": {
      "path": "/path/to/file",
      "content": "file content"
    }
  }
}
```

### Output (stdout)

```json
{
  "action": "allow",
  "modified_data": null,
  "message": null
}
```

### Response Actions

| Action | Effect |
|--------|--------|
| `allow` | Continue execution |
| `block` | Abort execution |
| `modify` | Continue with modified data |

## Use Cases

### Security Validation

Block writes to sensitive files:

```python
if ".env" in path or "credentials" in path:
    sys.exit(2)  # Block
```

### Context Injection

Add git context before agent planning:

```python
if event == "before_agent":
    git_log = subprocess.check_output(["git", "log", "-3", "--oneline"])
    data["context"] += f"\n\nRecent commits:\n{git_log}"
    print(json.dumps({"action": "modify", "modified_data": data}))
```

### Logging and Monitoring

Log all tool executions:

```python
if event == "after_tool":
    log_entry = {
        "tool": data["tool_name"],
        "success": data["success"],
        "timestamp": payload["timestamp"]
    }
    with open("tool_log.jsonl", "a") as f:
        f.write(json.dumps(log_entry) + "\n")
```

### Tool Filtering (RAG)

Dynamically filter available tools:

```python
if event == "before_tool_selection":
    prompt = data["prompt"].lower()
    # Only include relevant tools
    filtered_tools = [t for t in data["available_tools"]
                      if matches_prompt(t, prompt)]
    print(json.dumps({
        "action": "modify",
        "modified_data": {"available_tools": filtered_tools}
    }))
```

## Environment Variables

Available in hook scripts:

| Variable | Description |
|----------|-------------|
| `JOSHU_SESSION_ID` | Current session ID |
| `JOSHU_PROJECT_DIR` | Workspace path |
| `JOSHU_CONFIG_DIR` | Config directory |

## Best Practices

### Security
- Validate all input data
- Set appropriate timeouts
- Limit permissions of hook scripts
- Sandbox untrusted hooks

### Performance
- Optimize for fast execution
- Use caching where possible
- Choose appropriate hook events
- Avoid blocking operations

### Debugging
- Log to stderr for debugging output
- Use the `/hooks` panel command to view status
- Test hooks in isolation first

## See Also

- [Tool Calling](tool-calling.md) - Built-in tools reference
- [Extensions](extensions.md) - Extension system
- [Configuration](configuration.md) - Configuration guide
