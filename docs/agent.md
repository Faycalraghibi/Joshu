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

## Undo

Before `replace` or `write_file` changes a file, the agent records the file's
original content (or that it didn't exist). `/undo` reverts every file the
agent edited for its most recent request, newest first on repeated use, and
the model is told at the start of the next request. Changes made through shell
commands are not tracked.

## Sessions

Every conversation is saved after each request to
`~/.joshu/sessions/<id>.json` (set `JOSHU_HOME` to move it, or
`save_sessions: false` to turn it off). An interrupted request is saved too.

```bash
joshu sessions                         # sessions started in this directory (--all for every one)
joshu run --continue "and now the tests"
joshu run --resume 3f2a9c "pick up where we left off"
joshu interactive --continue
```

In interactive mode, `/resume` lists recent sessions and `/resume <id>`
continues one. A unique prefix of the id is enough. Headless JSON output
includes `session_id`, so scripts can continue a conversation across calls.

## Custom commands

Reusable prompts are files in `.joshu/commands/` (project) or
`~/.joshu/commands/` (user); project files win on a name clash. Run one as
`/name args` in interactive mode, or `joshu run "/name args"`; `/commands`
lists them.

Markdown: the body is the prompt, `$ARGUMENTS` or `{{args}}` is replaced by
the text after the command name (or the text is appended if neither appears).

```markdown
---
description: Review a file for bugs
---
Review $ARGUMENTS for bugs and risky patterns. Report file:line for each issue.
```

TOML: same format as extension commands, with an optional `shell` step whose
output fills `{{shell_output}}`. The shell step needs the same approval as the
agent's shell tool.

```toml
description = "Explain the working tree changes"
shell = "git diff --stat"
prompt = "Explain these changes:\n{{shell_output}}\n{{args}}"
```

Built-in commands (`/help`, `/undo`, ...) can't be overridden.

## Sub-agents

The `task` tool hands a self-contained job to a sub-agent and returns its final
answer, keeping the main conversation small. By default it is a read-only
researcher. Define specialized ones in `.joshu/agents/` (project) or
`~/.joshu/agents/` (user):

```markdown
---
description: Reviews a change for bugs and risky patterns
tools: read_file, glob, search_file_content
model: openai/gpt-4.1          # optional: another model of the same provider
max_turns: 15                  # optional
---
You are a careful code reviewer. Report only real problems, with file:line.
```

The main agent sees each sub-agent's description and picks one by name. A
sub-agent with a `tools` list gets exactly those tools and uses the main
agent's permission gate, so its edits and commands still ask you. Without a
`tools` list it is read-only. `/agents` lists the defined sub-agents. YAML/JSON
definitions in the `joshu.agents` format also work (use `model_name: inherit`
for the main model).

## Configuration

| Key | Default | Meaning |
|---|---|---|
| `permission_mode` | `default` | See above |
| `agent_max_turns` | `50` | Model calls per request before stopping |
| `context_window` | `128000` | Model context size in tokens |
| `compact_threshold` | `0.8` | Fraction of the window that triggers compaction |
| `tool_output_limit` | `30000` | Max characters of one tool result sent to the model |
| `max_tokens` | `4096` | Max tokens per model response |
| `provider` | `openrouter` | Model provider (see `joshu providers`) |
| `providers` | `{}` | Custom providers and overrides |
| `fallback_providers` | `[]` | Tried when the provider can't be reached |
| `save_sessions` | `true` | Save conversations for `--resume` / `--continue` |
| `hooks` | `{}` | Commands run on agent events (see [Hooks](hooks.md)) |

## Interactive commands

- `/agent`, `/plan`, `/ask`: switch mode (`ask` answers without tools)
- `/permissions [mode]`: show or set the permission mode
- `/undo`: revert the agent's file edits from its last request
- `/resume [id]`: list saved sessions, or continue one
- `/commands`, `/agents`: list custom commands and sub-agents
- `/reset`: start a new agent conversation
- Ctrl+C: interrupt the current task; the conversation stays usable

## Hooks

Commands configured under `hooks:` run on `before_agent`, `after_agent`,
`before_tool` and `after_tool` (see [Hooks](hooks.md)). A `before_tool` hook
can block a call (the model is told why) or rewrite its arguments.
