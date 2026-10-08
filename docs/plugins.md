# Plugins

A plugin bundles skills, slash commands, output styles, hooks and MCP servers
so they can be shared and installed in one step.

```bash
joshu plugin install https://github.com/acme/joshu-release-tools.git
joshu plugin install acme/release-tools   # owner/repo on GitHub
joshu plugin install ./my-plugin          # a local directory
joshu plugin list                         # what is installed and what each adds
joshu plugin update release-tools         # again from where it came from
joshu plugin disable release-tools        # keep it installed but unused
joshu plugin enable release-tools
joshu plugin remove release-tools
```

`install` shows what the plugin adds and asks before installing (`--yes`
skips the question, `--force` replaces an installed plugin of the same name).
Hooks and MCP servers run commands on your machine: install plugins you
trust. Changes apply to new sessions.

## Layout

```
my-plugin/
  joshu-plugin.yaml
  skills/<name>/SKILL.md      as in .joshu/skills/
  commands/<name>.md          as in .joshu/commands/
  output-styles/<name>.md     as in .joshu/output-styles/
```

```yaml
# joshu-plugin.yaml
name: release-tools            # lowercase letters, digits, '.', '-', '_'
version: 1.2.0
description: Changelog and release helpers
hooks:                         # same form as `hooks:` in config.yaml
  stop:
    - python ${PLUGIN_DIR}/hooks/check.py
mcp_servers:                   # same form as `mcp_servers:` in config.yaml
  tracker:
    command: node
    args: ["${PLUGIN_DIR}/server.js"]
```

`${PLUGIN_DIR}` is replaced with the plugin's installed directory.

## Where they go and what wins

Plugins are installed in `~/.joshu/plugins/<name>/` (`$JOSHU_HOME/plugins`).
Their skills, commands and styles are found after the project's and your own,
so those win on a name clash; an MCP server configured in `config.yaml` or
`mcp.json` wins over a plugin's of the same name.

## Claude Code plugins and marketplaces

Plugins and marketplaces made for Claude Code install as they are:

```bash
joshu plugin marketplace add nykooi1/vibe-wise    # or, in a session: /plugin marketplace add ...
joshu plugin install vibe-wise@vibe-wise          # plugin@marketplace (or just the name)
joshu plugin marketplace list | update <name> | remove <name>
```

A marketplace is a repository with `.claude-plugin/marketplace.json`; it is
kept in `~/.joshu/plugins/.marketplaces/`, and `update` of a plugin installed
from one fetches the marketplace again first. A plugin's
`.claude-plugin/plugin.json` is read like `joshu-plugin.yaml`, and:

| Claude Code | In Joshu |
|---|---|
| `skills/`, `commands/` | Skills and slash commands (same formats) |
| `agents/*.md` | Sub-agents; tool names (`Read`, `Bash`, ...) are translated, model aliases (`sonnet`, ...) use the main model |
| `hooks/hooks.json` | Hooks: `SessionStart`, `UserPromptSubmit`, `PreToolUse`, `PostToolUse`, `PreCompact`, `Notification`, `Stop`, `SubagentStop`, `SessionEnd`, with their `matcher` (over Claude Code tool names); `command` and `prompt` hooks |
| `.mcp.json` | MCP servers |
| `${CLAUDE_PLUGIN_ROOT}` | The installed plugin's directory |

Hook scripts written for Claude Code work in Joshu generally (in plugins or
in `hooks:`): their input has `hook_event_name`, `session_id`, `cwd`,
`tool_name` / `tool_input` (Claude Code tool names), `prompt` and `source`
beside Joshu's own fields, and their output is understood
(`hookSpecificOutput.additionalContext`, `decision: "block"` with `reason`,
`permissionDecision: "deny"`, `continue: false`). On Windows, a hook command
starting with `python3` runs with the Python that exists.
