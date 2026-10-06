# Plugins

A plugin bundles skills, slash commands, output styles, hooks and MCP servers
so they can be shared and installed in one step.

```bash
joshu plugin install https://github.com/acme/joshu-release-tools.git
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
