# Configuration Guide

Complete guide to configuring Joshu for your needs.

## Configuration Methods

Joshu supports three configuration methods (in order of precedence):

1. **Command-line arguments** — Highest priority
2. **Environment variables** — `.env` file or system environment
3. **Config file** — `~/.joshu/config.yaml` (lowest priority)

## Config File

### Location

`~/.joshu/config.yaml` (created automatically on first run)

### Example Configuration

```yaml
# Model Settings
model: "llama-3-8b"
max_tokens: 4096
temperature: 0.1

# Safety Settings
safety_mode: true
auto_execute: false
sandbox_enabled: true

# Memory Settings
memory_enabled: true
history_size: 100

# Semantic Memory Settings
semantic_memory_enabled: true
semantic_memory_similarity_threshold: 0.3
semantic_memory_max_results: 5
semantic_memory_min_content_length: 10

# Interactive Mode Settings
interactive: true
multiline_input: true
vim_mode: false
persistent_history: true
history_limit: 1000

# Logging
log_level: "INFO"
```

## Environment Variables

### Essential Variables

Create a `.env` file in your project root or home directory:

```bash
# Model Configuration
JOSHU_MODEL=llama-3-8b
JOSHU_USE_CLOUD=true

# OpenRouter API (for cloud models)
OPENROUTER_API_KEY=your_api_key_here
OPENROUTER_MODEL=openai/gpt-4o-mini
OPENROUTER_SITE_URL=https://your-site.com
OPENROUTER_SITE_TITLE=Joshu Assistant

# Model-Specific API Keys (optional)
DEEPSEEK_API_KEY=your_key
TONGYI_API_KEY=your_key
QWEN_API_KEY=your_key
KIMI_DEV_API_KEY=your_key
GLM_API_KEY=your_key

# Configuration Options
JOSHU_MEMORY_ENABLED=true
JOSHU_SANDBOX_ENABLED=true
JOSHU_LOG_LEVEL=INFO
JOSHU_MAX_CONTEXT=4096

# Local Model Paths
LLAMA_CPP_MODEL_LLAMA3_8B=/path/to/llama-3-8b.gguf
LLAMA_CPP_MODEL_MISTRAL_7B=/path/to/mistral-7b.gguf
```

### Environment Variable Reference

| Variable | Default | Description |
|----------|---------|-------------|
| `JOSHU_MODEL` | `llama-3-8b` | Default model to use |
| `JOSHU_USE_CLOUD` | `false` | Use cloud models when available |
| `JOSHU_MEMORY_ENABLED` | `true` | Enable conversation memory |
| `JOSHU_SANDBOX_ENABLED` | `true` | Enable sandbox mode |
| `JOSHU_LOG_LEVEL` | `INFO` | Logging level (DEBUG, INFO, WARNING, ERROR) |
| `JOSHU_MAX_CONTEXT` | `4096` | Maximum context tokens |
| `OPENROUTER_API_KEY` | - | OpenRouter API key |
| `OPENROUTER_MODEL` | - | Specific OpenRouter model |

## CLI Configuration Management

Manage configuration from the command line:

### View Configuration

```bash
# List all options
joshu config --list

# Get specific value
joshu config --get model
joshu config --get safety_mode
```

### Set Configuration

```bash
# Set model
joshu config --set model=llama-3-70b

# Enable/disable features
joshu config --set auto_execute=true
joshu config --set safety_mode=false

# Semantic memory settings
joshu config --set semantic_memory_similarity_threshold=0.5
joshu config --set semantic_memory_max_results=10
```

### Reset Configuration

```bash
# Reset to defaults
joshu config --reset

# Edit config file directly
joshu config --edit
```

## Interactive Mode Configuration

### In-Session Configuration

While in interactive mode:

```
> /config
  [Shows all configuration]

> /config model
  model: llama-3-8b

> /config model llama-3-70b
  Set model = llama-3-70b
```

## Configuration Options Reference

### Model Settings

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `model` | string | `llama-3-8b` | AI model to use |
| `max_tokens` | integer | `4096` | Maximum tokens in context |
| `temperature` | float | `0.1` | Model temperature (0.0-1.0) |

### Safety Settings

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `safety_mode` | boolean | `true` | Enable command safety checks |
| `auto_execute` | boolean | `false` | Auto-execute safe commands |
| `sandbox_enabled` | boolean | `true` | Use sandbox for code execution |

### Memory Settings

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `memory_enabled` | boolean | `true` | Enable conversation memory |
| `history_size` | integer | `100` | Maximum history entries |

### Semantic Memory Settings

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `semantic_memory_enabled` | boolean | `true` | Enable semantic memory |
| `semantic_memory_similarity_threshold` | float | `0.3` | Similarity threshold (0.0-1.0) |
| `semantic_memory_max_results` | integer | `5` | Max search results |
| `semantic_memory_min_content_length` | integer | `10` | Min content length to store |

### Interactive Mode Settings

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `interactive` | boolean | `true` | interactive features |
| `multiline_input` | boolean | `true` | Support multiline input |
| `vim_mode` | boolean | `false` | Enable Vim keybindings |
| `persistent_history` | boolean | `true` | Persist command history |
| `history_limit` | integer | `1000` | Max history entries |

### Tool Calling Settings

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `tool_calling_enabled` | boolean | `true` | Enable automatic tool calling |
| `tool_calling_max_iterations` | integer | `3` | Max tool call iterations per query |
| `web_search_tool_enabled` | boolean | `true` | Enable web search tool |

### Web Search Settings

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `web_search_enabled` | boolean | `true` | Enable web search functionality |
| `web_search_max_results` | integer | `5` | Default max search results |
| `web_search_timeout` | integer | `10` | Search timeout in seconds |

### Web Fetch Settings

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `web_fetch_enabled` | boolean | `true` | Enable web fetch functionality |
| `web_fetch_timeout` | integer | `15` | Fetch timeout in seconds |
| `web_fetch_max_content_length` | integer | `50000` | Max characters to return |

### MCP Server Settings

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `mcp_enabled` | boolean | `true` | Enable MCP integration |
| `mcp_discovery_on_startup` | boolean | `true` | Auto-discover MCP tools on startup |
| `mcp_servers` | dict | `{}` | MCP server configurations |

**MCP Server Configuration Example:**

```yaml
mcp_enabled: true
mcp_discovery_on_startup: true

mcp_servers:
  github:
    transport: "stdio"
    command: "npx"
    args: ["-y", "@modelcontextprotocol/server-github"]
    enabled: true
```

**Using `mcp.json` (Claude Desktop compatible):**

Create `config/mcp.json` or `~/.joshu/mcp.json`:

```json
{
  "mcpServers": {
    "github": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-github"],
      "env": {
        "GITHUB_PERSONAL_ACCESS_TOKEN": "${GITHUB_TOKEN}"
      }
    }
  }
}
```

Environment variables in `env` values are expanded automatically using `${VAR_NAME}` syntax.

## Examples

### Configure for Maximum Safety

```yaml
safety_mode: true
auto_execute: false
sandbox_enabled: true
log_level: "DEBUG"
```

### Configure for Performance

```yaml
model: "llama-3-8b"
max_tokens: 2048
temperature: 0.0
auto_execute: true
```

### Configure for Cloud Models

```yaml
model: "gpt-4o-mini"
```

With `.env`:
```bash
JOSHU_USE_CLOUD=true
OPENROUTER_API_KEY=your_key
OPENROUTER_MODEL=openai/gpt-4o-mini
```

## Next Steps

- **[Model Setup](models.md)** — Configure local and cloud models
- **[OpenRouter Setup](openrouter.md)** — Cloud model configuration
- **[MCP Servers](mcp-servers.md)** — Integrate external tools via MCP
- **[Environment Variables](environment-variables.md)** — Complete reference
