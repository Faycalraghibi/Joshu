"""
Flags of `joshu run` that set up a run before the agent starts:
--allowed-tools, --disallowed-tools, --add-dir, --mcp-config and --settings.

They change the configuration for this process only (nothing is saved).
Tool rules take Joshu's names and Claude Code's (`Read`, `Bash(git log:*)`),
so scripts written for `claude -p` work.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from joshu.core.config import get_config_manager

# One rule: a name, optionally with a parenthesized pattern (which may hold spaces or commas)
_RULE = re.compile(r"[A-Za-z0-9_.-]+(?:\([^)]*\))?")
# Valid --session-id values
SESSION_ID = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


class RunOptionError(ValueError):
    """A flag's value can't be used."""


def tool_rules(values: Sequence[str]) -> List[str]:
    """
    Permission rules from --allowed-tools / --disallowed-tools values, in
    Joshu's form: `Bash(git log:*)` -> `run_shell_command(git log*)`,
    `Edit` -> `replace`. Each value may hold several rules, separated by
    commas or spaces.
    """
    from joshu.core.claude_compat import joshu_tool

    rules = []
    for value in values:
        for match in _RULE.finditer(value or ""):
            text = match.group(0)
            name, _, pattern = text.partition("(")
            name = joshu_tool(name)
            if not pattern:
                rules.append(name)
                continue
            pattern = pattern[:-1].strip()
            if pattern.endswith(":*"):  # Claude Code's prefix form
                pattern = pattern[:-2] + "*"
            rules.append(f"{name}({pattern})")
    return rules


def load_settings(value: str) -> Dict[str, Any]:
    """--settings: a JSON object, or a JSON / YAML file holding one."""
    text = value.strip()
    if not text.startswith("{"):
        path = Path(value).expanduser()
        try:
            text = path.read_text(encoding="utf-8")
        except OSError as e:
            raise RunOptionError(f"Can't read settings file {value}: {e}") from e
    try:
        data = json.loads(text)
    except ValueError:
        import yaml

        try:
            data = yaml.safe_load(text)
        except yaml.YAMLError as e:
            raise RunOptionError(f"Settings are neither JSON nor YAML: {e}") from e
    if not isinstance(data, dict):
        raise RunOptionError("Settings must be an object of setting: value")
    return data


def apply_run_options(
    allowed_tools: Sequence[str] = (),
    disallowed_tools: Sequence[str] = (),
    add_dirs: Sequence[str] = (),
    mcp_configs: Sequence[str] = (),
    settings: Optional[str] = None,
) -> None:
    """
    Apply the setup flags to this process's configuration.

    Raises:
        RunOptionError: a value can't be used (the message says why)
    """
    config = get_config_manager()
    if settings:
        for key, value in load_settings(settings).items():
            config.set(str(key), value)

    allow, deny = tool_rules(allowed_tools), tool_rules(disallowed_tools)
    if allow or deny:
        current = dict(config.get("permissions") or {})
        current["allow"] = list(current.get("allow") or []) + allow
        current["deny"] = list(current.get("deny") or []) + deny
        config.set("permissions", current)

    from joshu.tools.filesystem_tools import add_workspace_dir

    for directory in add_dirs:
        try:
            add_workspace_dir(directory)
        except ValueError as e:
            raise RunOptionError(f"--add-dir: {e}") from e

    if mcp_configs:
        from joshu.core.claude_compat import read_mcp_json

        servers = dict(config.get("mcp_servers") or {})
        for file in mcp_configs:
            path = Path(file).expanduser()
            if not path.is_file():
                raise RunOptionError(f"--mcp-config: no such file {file}")
            found = read_mcp_json(path, path.parent.resolve())
            if not found:
                raise RunOptionError(f"--mcp-config: no MCP servers in {file}")
            servers.update(found)
        config.set("mcp_servers", servers)
        config.set("mcp_enabled", True)


def check_session_id(session_id: str, resuming: bool, fork: bool) -> None:
    """
    --session-id names a new conversation: a valid id that isn't saved yet
    (with --resume / --continue it needs --fork-session: the copy gets the id).
    """
    from joshu.core.sessions import sessions_dir

    if not SESSION_ID.match(session_id):
        raise RunOptionError("--session-id: use 1-64 letters, digits, - or _")
    if resuming and not fork:
        raise RunOptionError("--session-id with --resume / --continue needs --fork-session")
    if (sessions_dir() / f"{session_id}.json").is_file():
        raise RunOptionError(f"Session {session_id} already exists: continue it with --resume")
