# Hooks System

Hooks let external commands inspect, block or modify what the agent does,
without changing Joshu's code.

## Overview

A hook is a shell command. When its event fires, Joshu runs it with a JSON
payload on stdin and waits for it to finish. The exit code decides what happens:

| Exit Code | Result |
|-----------|--------|
| 0 | Continue (stdout may carry a JSON response, see below) |
| 2 | Block; stderr (or the JSON `message`) is the reason given to the model |
| Other | Log a warning and continue |

Hooks fail open: a hook that crashes or times out does not block the agent.

## Hook Events

Events fired by the agent:

| Event | When | `data` in the payload | Blocking it |
|-------|------|------------------------|-------------|
| `session_start` | The first request of a session (new or resumed) | `cwd`, `model`, `resumed` | - |
| `before_agent` | A request is about to be handled | `prompt` | skips the request |
| `before_tool` | A tool call is about to run (before the permission prompt) | `tool_name`, `arguments` | skips the call; the model is told why |
| `after_tool` | A tool call finished | `tool_name`, `result`, `success` | - |
| `subagent_stop` | A sub-agent (`task`) finished | `description`, `response` | - |
| `pre_compress` | Context is about to be cleared or summarized | `kind` (`clear` / `summarize`), `tokens`, `window` | skips it this time |
| `notification` | Joshu needs you (an approval) | `message`, `tool_name` | - |
| `stop` | The agent is about to finish a request | `prompt`, `response`, `continues_so_far` | sends the agent back to work |
| `after_agent` | The agent finished a request | `prompt`, `response` | - |
| `session_end` | You leave Joshu, `/clear`, or a `joshu run` ends | `cwd` | - |

### Adding context

`session_start` and `before_agent` hooks can add information to the
conversation: print plain text, or reply with
`{"additional_context": "..."}`. It is added before the user's request, marked
`[Context from hooks]`. Typical uses: the current branch and open tickets, the
date of a code freeze, the output of `git status`.

### Keeping the agent working

A `stop` hook that blocks (exit code 2, or `{"action": "block"}`) sends the
agent back to work; its message (or stderr) tells the model why, e.g. "Run the
tests before finishing" or "The linter still reports errors". It can do so at
most 3 times per request, so a misbehaving hook can't keep the agent running
forever; `continues_so_far` tells the hook how many times it already did.

```yaml
hooks:
  stop:
    - command: python .joshu/hooks/require_green_tests.py
      timeout: 120
  notification:
    - powershell -c "[console]::beep(880, 200)"
```

## Configuration

Declare hooks in `config/config.yaml`:

```yaml
hooks:
  before_tool:
    - python .joshu/hooks/protect_secrets.py
    - command: ./scripts/audit.sh
      timeout: 30          # seconds (default 10)
  after_agent: python .joshu/hooks/notify.py
```

Each event takes one command or a list. An entry is either a command string or
a mapping with `command` and an optional `timeout`. Commands run through the
shell from the current directory. Unknown events and malformed entries are
reported when the agent starts. To act only on some tools, check
`data.tool_name` in the hook.

### Prompt hooks

Instead of a command, a hook can be a prompt that a model decides:

```yaml
hooks:
  before_tool:
    - prompt: "Refuse commands that delete or overwrite files outside the project: $ARGUMENTS"
      matcher: Bash
  stop:
    - prompt: "If code was changed and no tests were run, say what to check."
```

The model (`hook_model`, or the configured one) gets the prompt with the
event as JSON in place of `$ARGUMENTS` (or after the prompt) and answers
`{"ok": true}` or `{"ok": false, "reason": "..."}`. `ok: false` blocks the
event like a command exiting with code 2; for `stop` it sends the agent back to
work with the reason. If the model can't be reached or doesn't answer that way,
the event goes ahead and the problem is logged. Claude Code hooks of type
`prompt` (in plugins) work the same.

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
  "message": null,
  "additional_context": null
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

### Rewriting Tool Arguments

A `before_tool` hook can change a call's arguments by returning `modify`:

```python
if event == "before_tool" and data["tool_name"] == "run_shell_command":
    command = data["arguments"]["command"]
    if command.startswith("pytest") and "-q" not in command:
        data["arguments"]["command"] = command + " -q"
        print(json.dumps({"action": "modify", "modified_data": {"arguments": data["arguments"]}}))
```

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

- [Agent Tools](agent.md#tools) - Built-in tools reference
- [Configuration](configuration.md) - Configuration guide
