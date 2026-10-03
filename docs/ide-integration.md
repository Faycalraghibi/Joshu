# IDE Integration

Joshu integrates with IDEs like VS Code to provide contextual awareness and interactive features.

## Features

| Feature | Description |
|---------|-------------|
| **Editor Context** | Access open files, cursor position, selected text |
| **Native Diffing** | View proposed changes in IDE's diff viewer |
| **CLI Launch** | Start Joshu sessions from the IDE |

## CLI Commands

```bash
# Start the IDE server
joshu ide start

# Check connection status
joshu ide status

# Display current IDE context
joshu ide context

# Install VS Code extension
joshu ide install
```

## Architecture

```
┌─────────────────────────────────┐
│    VS Code Extension            │
│  • Monitors open files          │
│  • Tracks cursor & selection    │
└──────────────┬──────────────────┘
               │ POST /context
┌──────────────▼──────────────────┐
│    Python IDE Server            │
│  • Receives context updates     │
│  • Manages diff proposals       │
│  • Authenticates requests       │
└──────────────┬──────────────────┘
               │ GET /context
┌──────────────▼──────────────────┐
│       Joshu CLI                 │
│  • Queries IDE context          │
│  • Proposes code changes        │
└─────────────────────────────────┘
```

## Context Information

The IDE provides context to Joshu:

```json
{
  "workspace_path": "/path/to/project",
  "active_file": "src/main.py",
  "cursor_position": {"line": 42, "column": 10},
  "selected_text": "def process_data():\n    ...",
  "recent_files": [
    {"path": "src/main.py", "language": "python"},
    {"path": "tests/test_main.py", "language": "python"}
  ]
}
```

### Limits

| Property | Limit |
|----------|-------|
| Recent files | 10 files max |
| Selected text | 16 KB max |

## Diff Proposals

When Joshu proposes file changes:

1. CLI calls `POST /diff/propose` with original and proposed content
2. IDE displays native diff view
3. User accepts or rejects changes
4. CLI receives notification via callback

```python
from joshu.ide import get_ide_client

client = get_ide_client()
if client:
    proposal_id = client.propose_diff(
        file_path="/path/to/file.py",
        original_content="old code",
        proposed_content="new code",
        description="Refactored function"
    )
```

## Security

| Measure | Implementation |
|---------|---------------|
| Authentication | Bearer token in headers |
| Binding | 127.0.0.1 only (localhost) |
| Discovery | Temp file with restricted permissions |

## Server Discovery

The IDE server writes connection info to a temp file:

```
{TEMP}/joshu-ide-server-{PID}-{PORT}.json
```

The CLI scans for these files to find running servers.

## VS Code Extension

### Installation

```bash
# Build extension
cd packages/vscode-joshu-companion
npm install
npm run build

# Install in VS Code
code --install-extension .
```

### Commands

| Command | Description |
|---------|-------------|
| `Joshu: Run` | Launch Joshu CLI in terminal |
| `Joshu: Send Selection` | Send selected text to session |
| `Joshu: Show Status` | Display connection status |

### Configuration

```json
{
  "joshu.serverPort": 0,
  "joshu.autoConnect": true,
  "joshu.contextLimit": 16384,
  "joshu.recentFilesLimit": 10
}
```

## Troubleshooting

### Server Not Found

1. Start the server: `joshu ide start`
2. Check status: `joshu ide status`
3. Ensure VS Code extension is installed

### Connection Issues

1. Verify server is running on expected port
2. Check temp directory for server info files
3. Restart IDE server: `joshu ide start`

## API Reference

### Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/context` | Update IDE context |
| GET | `/context` | Get current context |
| POST | `/diff/propose` | Propose a code change |
| POST | `/diff/{id}/accept` | Accept a proposal |
| POST | `/diff/{id}/reject` | Reject a proposal |
| GET | `/diff/pending` | List pending proposals |
| GET | `/health` | Health check |

## See Also

- [Hooks](hooks.md) - Extend agent behavior
- [Extensions](extensions.md) - Create extensions
- [Agent Tools](agent.md#tools) - Built-in tools
