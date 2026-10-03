# Agent

Joshu's agent works on a task with tools: it reads and searches files, edits
them, and runs commands, and it sees each result before deciding the next step.
It keeps going until it can answer without calling another tool.

## Running it

```bash
joshu run "add a --verbose flag to the CLI and test it"   # one task, approvals in the terminal
joshu interactive                                          # conversation; /agent mode is the default
```

Headless (scripts, CI):

```bash
joshu run -p "summarize what src/joshu/core/agent.py does"
joshu run --output-format json "list the TODOs in src/"
```

`-p` / `--print` prints only the final answer. `--output-format json` prints one
JSON object: `result`, `turns`, `tool_calls`, `usage`, `model`, `session_id`.
Headless runs can't ask for approval, so tools that need it are denied unless
the permission mode allows them.

`joshu run --legacy "..."` keeps the old behavior: translate the request into a
single shell command and run it after confirmation.

## Model provider

The agent works with any provider that has an OpenAI-compatible API and a
model with tool calling: OpenRouter, OpenAI, Anthropic, Gemini, Groq, Mistral,
local servers like Ollama or LM Studio, or a custom endpoint. Pick one with
`provider` and `model` in config, or `--provider` / `--model` per run; list
them with `joshu providers`. See [Models & Providers](models-and-providers.md).

## Permissions

Every tool call passes a permission check before it runs.

| Mode | Behavior |
|---|---|
| `default` | Read-only tools run freely; edits, shell commands, web fetch and MCP tools ask first |
| `accept_edits` | File edits run without asking; shell commands still ask |
| `plan` | Read-only: anything that changes state is denied |
| `bypass` | Everything runs |

In every mode, a shell command flagged by the safety check asks for an explicit
yes (and is denied in headless runs).

Approval prompts show a diff for edits and the command line for shell calls.
Answer `y` (yes), `a` (always: stop asking for this tool, or for this
program and subcommand such as `git status`, for the rest of the session) or
`n` (no; the model is told the call was denied).

Set the mode with `--permission-mode`, `-y` (bypass), the `permission_mode`
config value, or `/permissions <mode>` in interactive mode. `/plan` switches to
plan mode.

## Tools

| Tool | Purpose | Asks first |
|---|---|---|
| `read_file`, `list_directory`, `glob`, `search_file_content` | Explore the workspace | no |
| `replace` | Exact-string edit | yes |
| `write_file` | Create or overwrite a file | yes |
| `run_shell_command` | Run a command (fresh shell each call) | yes |
| `web_search` / `web_fetch` | Search the web / fetch a URL | no / yes |
| `write_todos`, `save_memory` | Track steps / remember facts in JOSHU.md | no |
| `task` | Delegate research to a read-only sub-agent | no |
| MCP tools | Tools from configured MCP servers | yes |

## Context

- The system prompt includes the working directory, OS, shell, date, git
  branch, the project `config/JOSHU.md` and user memory.
- When the conversation reaches `compact_threshold × context_window` (estimated
  tokens), older turns are replaced by a model-written summary; the most recent
  turns stay verbatim.
- Long tool output is cut to `tool_output_limit` characters (head and tail kept).

## Configuration

| Key | Default | Meaning |
|---|---|---|
| `permission_mode` | `default` | See above |
| `agent_max_turns` | `50` | Model calls per request before stopping |
| `context_window` | `128000` | Model context size in tokens |
| `compact_threshold` | `0.8` | Fraction of the window that triggers compaction |
| `tool_output_limit` | `30000` | Max characters of one tool result sent to the model |
| `max_tokens` | `4096` | Max tokens per model response |
| `provider` | `auto` | Model provider (see `joshu providers`) |
| `providers` | `{}` | Custom providers and overrides |
| `fallback_providers` | `[]` | Tried when the provider can't be reached |

## Interactive commands

- `/agent`, `/plan`, `/ask`: switch mode (`ask` answers without tools)
- `/permissions [mode]`: show or set the permission mode
- `/reset`: start a new agent conversation
- Ctrl+C: interrupt the current task; the conversation stays usable

## Hooks

`before_agent`, `before_tool` and `after_tool` hooks run around the loop (see
[Hooks](hooks.md)). A `before_tool` hook can block a call or replace its
arguments.
