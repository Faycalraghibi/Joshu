# Python SDK and streaming

Joshu can be driven from Python code or from another program through JSON
lines, using the same agent as the terminal.

## Python

```python
from joshu import Session, run

# One request
result = run("Fix the failing test in calc.py", permission_mode="accept_edits")
print(result.text)        # the agent's answer
print(result.usage)       # {"prompt_tokens": ..., "completion_tokens": ..., "cached_tokens": ...}

# A conversation
with Session(cwd="path/to/project", on_event=print) as session:
    session.send("Read the README and summarize it")
    session.send("Now list the open TODOs")       # remembers the first answer

# Events as they happen
with Session() as session:
    for event in session.stream("Explain src/app.py"):
        if event["type"] == "tool_use":
            print("using", event["name"], event["input"])
        elif event["type"] == "result":
            print(event["text"])
```

### Session options

| Option | Meaning |
|---|---|
| `model`, `provider` | Override the configured model / provider (named models work) |
| `permission_mode` | `default`, `accept_edits`, `plan` (read-only) or `bypass` |
| `cwd` | Project directory; file tools work inside it (one workspace per process) |
| `tools` | Only offer these tools, e.g. `["read_file", "search_file_content"]` |
| `can_use_tool` | `(name, input) -> bool`, decides calls that need approval; without it they're denied |
| `ask_user` | `(questions) -> answers`, answers the agent's multiple-choice questions (`joshu.core.ask.Question`: `question`, `options` as `(label, description)`, `multi_select`, `header`); return one answer per question (a list of chosen labels, typed text, or `None` to skip) or `None`. Without it the agent isn't offered the `ask_user` tool |
| `system_prompt` | Replace the generated system prompt |
| `on_event` | Called with every event |
| `stream_text` | Also emit `text` events while the model writes |
| `load_mcp` | Start the configured MCP servers and offer their tools |
| `persist` | Save the conversation like the CLI does |
| `resume` | Continue a saved session: its id, or `"last"` |
| `max_turns` | Model calls per request before stopping |
| `client` | A ready chat client (anything with `complete(...)`) instead of `model` / `provider` |

`send()` returns a `Result`: `text`, `session_id`, `turns`, `tool_calls`,
`usage` (this request), `cost_usd`, `model`, `stopped` (`max_turns`, `loop`,
`denied`, ... when cut short) and the raw `metadata`. `close()` (or leaving the
`with` block) runs `session_end` hooks. Configuration, hooks, memory, skills
and secret protection apply as in the terminal.

### Events

| `type` | Fields |
|---|---|
| `text` | `text` (a streamed piece; only with `stream_text=True`) |
| `assistant` | `text`, `tool_calls` (`[{"name", "input"}]`): one model response |
| `tool_use` | `name`, `input`: a tool is about to run (after approval) |
| `tool_result` | `name`, `output`, `success` |
| `compact` | `tokens_before`, `tokens_after` |
| `result` | `text`, `session_id`, `turns`, `tool_calls`, `usage`, `cost_usd`, `model`, `stopped` |

## JSON lines from the command line

```bash
joshu run --output-format stream-json "What does calc.py do?"
```

prints one JSON object per line as things happen: first
`{"type": "system", "session_id", "model", "cwd", "tools"}`, then the events
above, ending with `result`. Errors are `{"type": "error", "message"}` (exit
code 1).

With `--input-format stream-json`, requests come from stdin, one per line, all
in one conversation:

```bash
printf '%s\n' \
  '{"type": "user", "content": "What does calc.py define?"}' \
  '{"type": "user", "content": "And how many lines does it have?"}' \
  | joshu run --input-format stream-json --output-format stream-json
```

`content` may also be a list of `{"type": "text", "text": ...}` parts, and a
plain text line is taken as a request. Tools that need approval are denied
unless `--permission-mode` (or `-y` for bypass) allows them.
