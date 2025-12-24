# Extensions Framework

Joshu's extensions framework enables packaging custom tools, commands, MCP servers, and context files. Extensions follow a simple manifest-based structure and can be installed from Git repositories or developed locally.

## Quick Start

### Create a New Extension

```bash
# Create basic extension
joshu extension new my-extension

# Create with MCP server template
joshu extension new my-server --template mcp-server
```

### Install an Extension

```bash
# From Git repository
joshu extension install https://github.com/user/my-extension

# With specific branch/tag
joshu extension install https://github.com/user/my-extension --ref v1.0.0
```

### Link for Development

```bash
cd my-extension
joshu extension link .
```

## Extension Structure

```
my-extension/
├── joshu-extension.json    # Manifest (required)
├── JOSHU.md                # Context for LLM (optional)
├── commands/               # TOML-based custom commands
│   └── deploy.toml
├── tools/                  # Python tool handlers
│   └── my_tool.py
└── .env                    # Extension settings
```

## Manifest File

The `joshu-extension.json` manifest defines extension metadata and components:

```json
{
  "name": "my-extension",
  "version": "1.0.0",
  "description": "My custom extension",
  "author": "Your Name",
  "contextFileName": "JOSHU.md",
  "mcpServers": {
    "main": {
      "command": "node",
      "args": ["dist/index.js"],
      "transport": "stdio"
    }
  },
  "tools": [
    {
      "name": "my_tool",
      "description": "Does something useful",
      "handler": "tools/my_tool.py",
      "parameters": {
        "type": "object",
        "properties": {
          "input": {"type": "string"}
        }
      }
    }
  ],
  "commands": {
    "deploy": {
      "description": "Deploy the application",
      "handler": "commands/deploy.py"
    }
  }
}
```

## CLI Commands

| Command | Description |
|---------|-------------|
| `joshu extension list` | List installed extensions |
| `joshu extension install <url>` | Install from Git |
| `joshu extension uninstall <name>` | Remove extension |
| `joshu extension enable <name>` | Enable extension |
| `joshu extension disable <name>` | Disable extension |
| `joshu extension update [name]` | Update extension(s) |
| `joshu extension link .` | Link local directory |
| `joshu extension new <name>` | Create new extension |
| `joshu extension settings list <name>` | View settings |
| `joshu extension settings set <name> KEY VALUE` | Set setting |

### Scope Options

Enable/disable commands support `--scope` for user or workspace-level control:

```bash
joshu extension enable my-ext --scope workspace
joshu extension disable my-ext --scope user
```

## Custom Commands (TOML)

Define commands in `commands/*.toml` files:

```toml
# commands/deploy.toml
[command]
description = "Deploy to specified environment"
prompt = "Deploy to {{environment}} environment"
shell = "git push origin {{branch}}"

[command.args]
environment = { description = "Target environment", required = true }
branch = { default = "main" }
```

### Placeholders

| Placeholder | Description |
|-------------|-------------|
| `{{args}}` | Raw command arguments |
| `{{shell_output}}` | Output from shell command |
| `{{custom_name}}` | Any custom argument |

## Context Files

Extensions can provide context to the LLM via `JOSHU.md`:

```markdown
# My Extension

This extension provides tools for deployment.

## Available Tools
- `deploy_app`: Deploys application to cloud
- `rollback`: Reverts to previous version

## Usage Guidelines
Always confirm before deploying to production.
```

## Settings Management

Extensions can define configurable settings stored in `.env`:

```bash
# View settings
joshu extension settings list my-extension

# Set a value
joshu extension settings set my-extension API_KEY sk-xxx
```

Sensitive settings are stored in the system keychain when `keyring` is available.

## Variable Substitution

Manifest paths support variables:

| Variable | Resolves To |
|----------|-------------|
| `${extensionPath}` | Extension install directory |
| `${workspacePath}` | Current workspace root |
| `${homePath}` | User home directory |

## MCP Server Integration

Extensions can bundle MCP servers:

```json
{
  "mcpServers": {
    "my-server": {
      "command": "python",
      "args": ["-m", "my_mcp_server"],
      "transport": "stdio",
      "env": {
        "API_KEY": "${extensionPath}/.env"
      }
    }
  }
}
```

## Development Workflow

1. **Create**: `joshu extension new my-ext`
2. **Develop**: Edit files, add tools/commands
3. **Link**: `joshu extension link .`
4. **Test**: Use Joshu CLI to test tools
5. **Iterate**: Changes are reflected immediately

## Distribution

### Git Repository

Push to GitHub and install via URL:

```bash
joshu extension install https://github.com/user/my-extension
```

### Versioning

Use Git tags for version control:

```bash
joshu extension install https://github.com/user/my-extension --ref v1.0.0
```

## Conflict Resolution

- Extension commands are prefixed if they conflict with built-in commands (e.g., `/ext.deploy`)
- Workspace configurations take precedence over extension configurations
- Use `include_tools`/`exclude_tools` in MCP server config to filter tools

## See Also

- [MCP Servers](mcp-servers.md) - MCP protocol integration
- [Tool Calling](tool-calling.md) - Built-in tools guide
- [Configuration](configuration.md) - Global configuration
