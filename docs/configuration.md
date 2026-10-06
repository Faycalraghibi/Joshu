# Configuration Guide

Settings come from YAML files, later ones winning:

| Layer | File | Notes |
|---|---|---|
| Defaults | built in | |
| Install | `config/config.yaml` in a source checkout | Read-only |
| User | `~/.joshu/config.yaml` (`$JOSHU_HOME/config.yaml`) | `joshu config --set` writes here, only the keys you set |
| Project | `.joshu/config.yaml` in the project (nearest one above the current directory) | Only applies to projects you trust |

Command-line flags such as `--provider`, `--model` and `--permission-mode`
override all files for one run. `joshu config --list` shows the effective
settings and which files they came from.

Unknown keys are ignored; values of the wrong type are replaced by the default
with a warning.

Per-user data (saved sessions, input history, memory, semantic-memory
database) lives in `~/.joshu`, or in `$JOSHU_HOME` when set. Joshu doesn't
write files into your project directory.

### Trusting a project

A project config can set hooks and check commands (which run automatically)
and custom providers (which decide where your code and API keys go), so a
config in a repository you cloned is ignored until you trust that project:

```bash
joshu trust                 # trust the current directory (shows what its config sets)
joshu trust --list
joshu trust --remove
```

Joshu mentions an ignored project config when it starts. A project config
can't add itself to `trusted_projects`.

## Example

```yaml
# Model
provider: nvidia
model: nvidia/nemotron-3.5-lightning-30b-a3b
max_tokens: 8192
temperature: 0.1

# Agent
permission_mode: default        # default | accept_edits | plan | bypass
agent_max_turns: 50
context_window: 128000
compact_threshold: 0.8
tool_output_limit: 16000
sandbox_enabled: true

# Interactive mode
vim_mode: false
history_limit: 1000

```

## API keys

Each provider reads its key from one environment variable, e.g.
`OPENROUTER_API_KEY`, `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`. Put them in `.env`
at the project root:

```bash
OPENROUTER_API_KEY=your_key
```

`joshu providers` lists every provider, its key variable and whether the key is
set. See [Models & Providers](models-and-providers.md).

## Managing configuration

```bash
joshu config --list                 # show all values
joshu config --get model
joshu config --set provider=anthropic
joshu config --set model=claude-sonnet-5-5
joshu config --reset                # back to defaults
joshu config --edit                 # open the file in $EDITOR
```

In interactive mode: `/config`, `/config <key>`, `/config <key> <value>`;
`/permissions <mode>` changes the permission mode.

## Reference

### Model

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `provider` | string | `nvidia` | Model provider (see `joshu providers`) |
| `model` | string | `nvidia/nemotron-3.5-lightning-30b-a3b` | Model id for the provider |
| `providers` | dict | `{}` | Custom providers and overrides of built-in ones |
| `fallback_providers` | list | `[]` | Providers or named models tried when the main model can't serve a request |
| `models` | map | `{}` | Named models: `provider`, `model`, `context_window` |
| `request_retries` | integer | `3` | Retries per request on connection errors, 408/409/429 and 5xx |
| `request_timeout` | number | `120` | Seconds to wait for a model response |
| `max_tokens` | integer | `8192` | Max output tokens per model response; a response cut off at this limit is continued with a higher one (up to 32,768) |
| `temperature` | float | `0.1` | Sampling temperature for ask mode |

### Agent

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `permission_mode` | string | `default` | `default`, `accept_edits`, `plan` or `bypass` |
| `agent_max_turns` | integer | `50` | Model calls per request before stopping |
| `repo_map` | string | `auto` | A map of the project's files and definitions in the system prompt: `auto` (when the project fits, about 1,500 tokens), `always` (cut to fit), `never` |
| `max_budget_usd` | number | `0` | Stop when the session has cost this much in USD; 0 = no limit. Models without a known price (`model_pricing`, or a provider-reported cost) count as free |
| `max_request_tokens` | integer | `0` | Stop a request after it has used this many prompt + completion tokens; 0 = no limit |
| `self_review` | boolean | `true` | Before finishing a request that edited files or ran commands, the agent checks its work against the request once (one extra model call) |
| `context_window` | integer | `128000` | Model context size in tokens |
| `clear_tool_results_at` | integer | `60000` | Clear old tool results past this many tokens (at most half the window; 0 = never) |
| `compact_threshold` | float | `0.8` | Fraction of the window that triggers compaction |
| `tool_output_limit` | integer | `16000` | Max characters of one tool result sent to the model |
| `sandbox_enabled` | boolean | `true` | Stricter shell safety check (flags all destructive commands) |
| `permissions` | dict | `{allow: [], deny: []}` | Persistent permission rules (see [Agent](agent.md#permissions)) |
| `trusted_projects` | list | `[]` | Projects whose `.joshu/config.yaml` applies (`joshu trust`) |
| `save_sessions` | boolean | `true` | Save conversations for `--resume` / `--continue` |
| `hooks` | dict | `{}` | Commands run on agent events (see [Hooks](hooks.md)) |
| `diagnostics_enabled` | boolean | `true` | Check files after the agent edits them |
| `diagnostics` | dict | `{}` | Per-extension check commands (`{file}` placeholder) |
| `shell_sandbox` | dict | `{mode: off}` | OS sandbox for shell commands (see [Agent](agent.md#shell-sandbox)) |
| `model_pricing` | dict | `{}` | USD per million tokens, for providers that don't report cost |

### Memory and context

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `auto_memory` | boolean | `true` | Agent keeps notes across sessions (`memory` tool) |
| `lsp` | map / `false` | `{}` | Language server command per language (`""` disables one); `false` turns them off |
| `parallel_tools` | boolean | `true` | Run several read-only tool calls from one turn at the same time |
| `protected_paths` | list | `[]` | More file patterns that need approval to read or edit |
| `allow_paths` | list | `[]` | Exceptions to the protected file patterns |
| `mask_secrets` | boolean | `true` | Mask API keys and tokens in tool output |
| `defer_mcp_tools` | string | `auto` | Load MCP tool definitions on demand: `auto`, `always`, `never` |
| `theme` | string | `dark` | Color theme: `dark`, `light`, `colorblind`, `plain` |
| `output_style` | string | `default` | Reply style: `default`, `concise`, `explanatory`, `learning` or a custom one |
| `statusline` | string | `""` | Command whose output is shown under the input |
| `notifications` | string | `auto` | When a request that ran `notify_after_seconds` or longer finishes or waits for approval: `auto` sends a desktop notification where the terminal supports it (iTerm2, WezTerm, Ghostty, kitty) and rings the bell elsewhere; `desktop`, `bell`, or `off` |
| `notify_after_seconds` | integer | `20` | How long a request runs before it notifies |
| `semantic_memory_similarity_threshold` | float | `0.3` | Similarity threshold (0.0-1.0) |
| `semantic_memory_max_results` | integer | `5` | Max search results |
| `semantic_memory_min_content_length` | integer | `10` | Min content length to store |
| `attention_enabled` | boolean | `true` | Rank past turns by relevance and recency |
| `attention_similarity_weight` | float | `0.8` | Weight of relevance |
| `attention_recency_weight` | float | `0.2` | Weight of recency |
| `max_context_turns` | integer | `10` | Past turns considered |

### Interactive mode

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `interactive` | boolean | `true` | Interactive features |
| `vim_mode` | boolean | `false` | Enable Vim keybindings |
| `history_limit` | integer | `1000` | Max history entries |

### Web search

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `web_search_enabled` | boolean | `true` | Enable web search |
| `web_search_max_results` | integer | `5` | Default max search results |
| `web_search_timeout` | integer | `10` | Search timeout in seconds |

### MCP servers

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `mcp_enabled` | boolean | `true` | Enable MCP integration |
| `mcp_discovery_on_startup` | boolean | `true` | Discover MCP tools on startup |
| `mcp_servers` | dict | `{}` | MCP server configurations |

```yaml
mcp_servers:
  github:
    transport: "stdio"
    command: "npx"
    args: ["-y", "@modelcontextprotocol/server-github"]
    enabled: true
```

Servers can also be declared in `config/mcp.json` (Claude Desktop format);
`${VAR_NAME}` in `env` values is expanded from the environment:

```json
{
  "mcpServers": {
    "github": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-github"],
      "env": { "GITHUB_PERSONAL_ACCESS_TOKEN": "${GITHUB_TOKEN}" }
    }
  }
}
```

### Logging

| Option | Type | Default | Description |
|--------|------|---------|-------------|

## Next steps

- **[Models & Providers](models-and-providers.md)**: choose and add providers
- **[Agent](agent.md)**: permissions, tools and headless mode
- **[MCP Servers](mcp-servers.md)**: external tools via MCP
