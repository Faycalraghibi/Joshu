# Configuration Guide

Joshu reads its settings from `config/config.yaml` in the project (created with
defaults on first run) and API keys from the environment or a `.env` file.
Command-line flags such as `--provider`, `--model` and `--permission-mode`
override the file for one run.

Unknown keys in the file are ignored; values of the wrong type are replaced by
the default with a warning.

Per-user data (saved sessions, input history, memory, semantic-memory
database) lives in `~/.joshu`, or in `$JOSHU_HOME` when set. Joshu doesn't
write files into your project directory.

## Example

```yaml
# Model
provider: openrouter
model: poolside/laguna-s-2.1:free
max_tokens: 4096
temperature: 0.1

# Agent
permission_mode: default        # default | accept_edits | plan | bypass
agent_max_turns: 50
context_window: 128000
compact_threshold: 0.8
tool_output_limit: 30000
sandbox_enabled: true

# Interactive mode
multiline_input: true
vim_mode: false
persistent_history: true
history_limit: 1000

log_level: INFO
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
| `provider` | string | `openrouter` | Model provider (see `joshu providers`) |
| `model` | string | `poolside/laguna-s-2.1:free` | Model id for the provider |
| `providers` | dict | `{}` | Custom providers and overrides of built-in ones |
| `fallback_providers` | list | `[]` | Providers tried when the main one can't be reached |
| `max_tokens` | integer | `4096` | Max tokens per model response |
| `temperature` | float | `0.1` | Sampling temperature for ask mode |

### Agent

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `permission_mode` | string | `default` | `default`, `accept_edits`, `plan` or `bypass` |
| `agent_max_turns` | integer | `50` | Model calls per request before stopping |
| `context_window` | integer | `128000` | Model context size in tokens |
| `compact_threshold` | float | `0.8` | Fraction of the window that triggers compaction |
| `tool_output_limit` | integer | `30000` | Max characters of one tool result sent to the model |
| `sandbox_enabled` | boolean | `true` | Stricter shell safety check (flags all destructive commands) |
| `save_sessions` | boolean | `true` | Save conversations for `--resume` / `--continue` |
| `hooks` | dict | `{}` | Commands run on agent events (see [Hooks](hooks.md)) |
| `diagnostics_enabled` | boolean | `true` | Check files after the agent edits them |
| `diagnostics` | dict | `{}` | Per-extension check commands (`{file}` placeholder) |
| `shell_sandbox` | dict | `{mode: off}` | OS sandbox for shell commands (see [Agent](agent.md#shell-sandbox)) |
| `model_pricing` | dict | `{}` | USD per million tokens, for providers that don't report cost |

### Memory and context

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `memory_enabled` | boolean | `true` | Enable conversation memory |
| `history_size` | integer | `100` | Maximum history entries |
| `semantic_memory_enabled` | boolean | `true` | Enable semantic memory (needs `pip install -e .[use]`) |
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
| `multiline_input` | boolean | `true` | Support multiline input |
| `vim_mode` | boolean | `false` | Enable Vim keybindings |
| `persistent_history` | boolean | `true` | Persist command history |
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
| `log_level` | string | `INFO` | DEBUG, INFO, WARNING or ERROR |

## Next steps

- **[Models & Providers](models-and-providers.md)**: choose and add providers
- **[Agent](agent.md)**: permissions, tools and headless mode
- **[MCP Servers](mcp-servers.md)**: external tools via MCP
