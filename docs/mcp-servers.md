# MCP Server Integration

Model Context Protocol (MCP) servers extend Joshu's capabilities by integrating external tools and resources. MCP servers act as a bridge, allowing the LLM to discover and execute tools beyond built-in functionalities.

## Quick Start

### Add an MCP Server

```bash
# Add a stdio-based server
joshu mcp add filesystem --command "npx" --args "-y @modelcontextprotocol/server-filesystem /data"

# Add an HTTP-based server
joshu mcp add github --url "https://api.example.com/mcp" --transport http
```

### List Servers

```bash
joshu mcp list
```

### Connect and Discover Tools

```bash
joshu mcp connect
joshu mcp discover
```

## Configuration

### Config File

Add MCP servers to `~/.joshu/config.yaml`:

```yaml
mcp_enabled: true
mcp_discovery_on_startup: true

mcp_servers:
  filesystem:
    command: "npx"
    args: ["-y", "@modelcontextprotocol/server-filesystem", "/data"]
    transport: "stdio"

  github:
    url: "https://api.example.com/mcp"
    transport: "http"
    include_tools:
      - "search_repositories"
    exclude_tools:
      - "delete_repository"
```

### Using `mcp.json` (Claude Desktop Compatible)

Joshu also supports the standard `mcp.json` format used by Claude Desktop. Create this file at:
- `config/mcp.json` (in your project)
- `~/.joshu/mcp.json` (user-level)
- `./mcp.json` (current directory)

```json
{
  "mcpServers": {
    "github": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-github"],
      "env": {
        "GITHUB_PERSONAL_ACCESS_TOKEN": "${GITHUB_TOKEN}"
      }
    },
    "filesystem": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-filesystem", "/data"]
    }
  }
}
```

**Environment Variable Expansion:** Use `${VAR_NAME}` syntax in `env` values. Variables are expanded from your environment (including `.env` files).

### Configuration Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `mcp_enabled` | boolean | `true` | Enable MCP integration |
| `mcp_discovery_on_startup` | boolean | `true` | Auto-discover tools on startup |
| `mcp_servers` | dict | `{}` | Server configurations |

### Server Configuration

| Field | Type | Description |
|-------|------|-------------|
| `transport` | string | `stdio` or `http` |
| `command` | string | Command for stdio transport |
| `args` | list | Command arguments |
| `url` | string | URL for HTTP transport |
| `enabled` | boolean | Enable/disable server |
| `timeout` | integer | Connection timeout (seconds) |
| `include_tools` | list | Whitelist of tool names |
| `exclude_tools` | list | Blacklist of tool names |

## CLI Commands

| Command | Description |
|---------|-------------|
| `joshu mcp list` | List all configured servers |
| `joshu mcp add <name>` | Add a new server |
| `joshu mcp remove <name>` | Remove a server |
| `joshu mcp status [name]` | Show server status |
| `joshu mcp connect [name]` | Connect to server(s) |
| `joshu mcp disconnect [name]` | Disconnect from server(s) |
| `joshu mcp discover` | Discover available tools |

## Transport Types

### Stdio (Default)

Spawns a subprocess and communicates via stdin/stdout:

```yaml
myserver:
  transport: "stdio"
  command: "python"
  args: ["-m", "my_mcp_server"]
  env:
    API_KEY: "${MY_API_KEY}"
```

### HTTP

Connects to a remote MCP server over HTTP:

```yaml
myserver:
  transport: "http"
  url: "https://api.example.com/mcp"
  timeout: 60
```

## Prompts and resources

Besides tools, MCP servers can offer prompts and resources:

- **Prompts** become slash commands named `/server:prompt`. Arguments are
  `key=value` pairs, or plain words that fill the prompt's arguments in order
  (the last one takes the rest of the line):

  ```
  /github:review_pr 123 security
  /github:review_pr number=123 focus=security
  ```

- **Resources** are attached by writing `@server:uri` in a message; the
  resource's content is added for the model:

  ```
  summarize @notes:todo://this-week
  ```

`/mcp` lists each server's tools, prompts and resources. Typing `/` shows the
prompts in the command menu.

## Security

- Tool names are sanitized to prevent conflicts
- Reserved tool names (`web_search`, etc.) cannot be overridden
- Schema validation prevents malformed tool definitions
- Use `include_tools`/`exclude_tools` to control available tools

## Example: GitHub Server

```yaml
mcp_servers:
  github:
    command: "npx"
    args: ["-y", "@modelcontextprotocol/server-github"]
    transport: "stdio"
    env:
      GITHUB_TOKEN: "${GITHUB_TOKEN}"
    include_tools:
      - "search_repositories"
      - "get_file_contents"
      - "create_issue"
```

## Troubleshooting

### Server Not Connecting

1. Check server is enabled: `joshu mcp status <name>`
2. Verify command exists: Run the command manually
3. Check logs: `joshu config --set log_level=DEBUG`

### Tools Not Discovered

1. Ensure server is connected: `joshu mcp connect`
2. Check include/exclude filters in config
3. Run `joshu mcp discover` to see available tools

### Connection Timeout

Increase timeout in server config:

```yaml
myserver:
  timeout: 60  # seconds
```

## See Also

- [Agent Tools](agent.md#tools)
- [Configuration Guide](configuration.md)
