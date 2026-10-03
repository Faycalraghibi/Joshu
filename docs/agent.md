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

## Images

Attach screenshots, diagrams or mockups by referencing them as `@path` in a
request, or with `--image` (repeatable):

```bash
joshu run "why does the layout in @screenshots/home.png overflow on mobile?"
joshu run --image error.png "explain this error dialog"
```

The same `@path` syntax works in interactive mode. PNG, JPEG, GIF and WebP
files up to 5 MB are sent to the model with the request; references to other
file types are left as text. The model must support images (most current
OpenAI, Anthropic and Gemini models, and many models on OpenRouter, do).

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

### Permission rules

Rules that last beyond the session go under `permissions` in config:

```yaml
permissions:
  allow:
    - run_shell_command(git status*)
    - run_shell_command(npm test*)
    - write_file(docs/*)
  deny:
    - write_file(.env*)
    - run_shell_command(git push*)
```

A rule is a tool name, optionally with a glob over its main argument (the
command for `run_shell_command`, the path for file tools, the URL for
`web_fetch`). Deny rules block the call without asking, in every mode. Allow
rules skip the prompt; commands flagged as unsafe still ask. In interactive
mode, `/permissions allow <rule>` and `/permissions deny <rule>` save a rule
to your user config.

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

## Instructions

Put instructions for the agent in Markdown files; all that apply are added to
its system prompt, least specific first:

| File | Applies to |
|---|---|
| `~/.joshu/AGENTS.md` | every project |
| `AGENTS.md` or `JOSHU.md` in the repository root | the repository |
| `AGENTS.md` or `JOSHU.md` in a subdirectory | work in that directory (and below) |
| `config/JOSHU.md` | the repository (older location) |

The repository root is the nearest directory with `.git` above the working
directory. Facts the agent saves with `save_memory` live in `~/.joshu/JOSHU.md`
and are included too.

## Context

- The system prompt includes the working directory, OS, shell, date, git
  branch, instruction files and saved memory (see Instructions).
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

## Checks after edits

After `replace` or `write_file` succeeds, the edited file is checked and any
problems are added to the tool result, so the agent fixes them in the same
request:

| Files | Check |
|---|---|
| `.py` | Syntax, plus ruff's error rules (undefined names, invalid code; no style) when ruff is installed |
| `.json`, `.yaml`, `.yml`, `.toml` | Must parse |
| `.js`, `.mjs`, `.cjs` | `node --check` when node is installed |

Add or replace checks per extension; `{file}` is the edited file and a
non-zero exit means problems:

```yaml
diagnostics:
  .go: go vet {file}
  .ts: npx tsc --noEmit {file}
  .py: ""        # turn the built-in Python check off
```

`diagnostics_enabled: false` turns checking off.

## Shell sandbox

Shell commands the agent runs (and custom-command shell steps) can run in an
OS-level sandbox: they can write only inside the working directory and temp
files, with no network unless allowed.

```yaml
shell_sandbox:
  mode: auto          # off (default) | auto | bubblewrap | seatbelt | docker
  network: false
  image: python:3.12-slim   # docker only
  auto_allow: true    # sandboxed commands run without asking
```

| Backend | Platform | Notes |
|---|---|---|
| `bubblewrap` | Linux | Needs `bwrap`; on Ubuntu 24.04, unprivileged user namespaces must be allowed |
| `seatbelt` | macOS | Uses the built-in `sandbox-exec` |
| `docker` | Any (incl. Windows) | Commands run in a Linux container with the project at `/workspace` |

`auto` picks the first backend that works. With `auto_allow`, sandboxed
commands skip the approval prompt; commands flagged as unsafe still ask, and
plan mode still denies the shell. If the requested sandbox isn't available,
Joshu says so at startup and commands run unsandboxed, needing approval as
before. With Docker, a command that times out stops waiting but the container
may keep running until it finishes.

## Cost

Each response's cost is added up for the conversation. OpenRouter reports the
cost of every request; for other providers, give prices in USD per million
tokens:

```yaml
model_pricing:
  gpt-4.1-mini: {input: 0.40, output: 1.60}
```

When a request's price is unknown the total is shown as unknown rather than
undercounted. The cost appears in the footer after each request, as
`cost_usd` in `--output-format json`, in `/cost`, and in saved sessions;
sub-agents are included.

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
| `fallback_providers` | `[]` | Providers or named models tried when the model can't serve a request |
| `request_retries` | `3` | Retries per model request (connection errors, 429, 5xx) |
| `save_sessions` | `true` | Save conversations for `--resume` / `--continue` |
| `hooks` | `{}` | Commands run on agent events (see [Hooks](hooks.md)) |
| `diagnostics_enabled` | `true` | Check files after edits |
| `diagnostics` | `{}` | Per-extension check commands |
| `shell_sandbox` | `{mode: off}` | OS sandbox for shell commands |
| `model_pricing` | `{}` | USD per million tokens, for providers that don't report cost |

## Interactive commands

- `/agent`, `/plan`, `/ask`: switch mode (`ask` answers without tools)
- `/permissions [mode]`: show or set the permission mode
- `/undo`: revert the agent's file edits from its last request
- `/cost`: tokens and cost of the conversation
- `/resume [id]`: list saved sessions, or continue one
- `/commands`, `/agents`: list custom commands and sub-agents
- `/reset`: start a new agent conversation
- Ctrl+C: interrupt the current task; the conversation stays usable

## Hooks

Commands configured under `hooks:` run on `before_agent`, `after_agent`,
`before_tool` and `after_tool` (see [Hooks](hooks.md)). A `before_tool` hook
can block a call (the model is told why) or rewrite its arguments.
