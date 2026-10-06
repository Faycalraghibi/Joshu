"""
Reading what was written for Claude Code: plugin hooks, hook input and
output, sub-agent tool names.

Claude Code names events and tools differently (PreToolUse / Bash where
Joshu has before_tool / run_shell_command). This module translates, so
Claude Code plugins (`.claude-plugin/plugin.json`, `hooks/hooks.json`,
`.mcp.json`, `agents/`) and hook scripts work in Joshu.
"""

from __future__ import annotations

import json
import re
import shutil
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

# Joshu event -> Claude Code event
EVENT_NAMES = {
    "session_start": "SessionStart",
    "session_end": "SessionEnd",
    "before_agent": "UserPromptSubmit",
    "before_tool": "PreToolUse",
    "after_tool": "PostToolUse",
    "pre_compress": "PreCompact",
    "notification": "Notification",
    "stop": "Stop",
    "subagent_stop": "SubagentStop",
}
JOSHU_EVENTS = {claude: joshu for joshu, claude in EVENT_NAMES.items()}

# Joshu tool -> Claude Code tool
TOOL_NAMES = {
    "run_shell_command": "Bash",
    "read_file": "Read",
    "write_file": "Write",
    "replace": "Edit",
    "multi_edit": "MultiEdit",
    "notebook_edit": "NotebookEdit",
    "glob": "Glob",
    "search_file_content": "Grep",
    "list_directory": "LS",
    "web_fetch": "WebFetch",
    "web_search": "WebSearch",
    "task": "Task",
    "write_todos": "TodoWrite",
    "bash_output": "BashOutput",
    "kill_bash": "KillShell",
}
JOSHU_TOOLS = {claude: joshu for joshu, claude in TOOL_NAMES.items()}
# Claude Code model aliases that mean "a model of the main provider": use the main model
MODEL_ALIASES = {"sonnet", "opus", "haiku", "inherit", "default", ""}


def claude_tool(name: str) -> str:
    return TOOL_NAMES.get(name, name)


def joshu_tool(name: str) -> str:
    return JOSHU_TOOLS.get(name.strip(), name.strip())


def hook_input(event: str, session_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
    """The fields a Claude Code hook script reads from stdin, for a Joshu event."""
    fields: Dict[str, Any] = {
        "hook_event_name": EVENT_NAMES.get(event, event),
        "session_id": session_id,
        "cwd": str(Path.cwd()),
        "transcript_path": "",
    }
    if "tool_name" in data:
        fields["tool_name"] = claude_tool(str(data["tool_name"]))
        arguments = dict(data.get("arguments") or {})
        if "path" in arguments:
            arguments.setdefault("file_path", arguments["path"])
        fields["tool_input"] = arguments
        if "result" in data:
            fields["tool_response"] = data["result"]
    if "prompt" in data:
        fields["prompt"] = data["prompt"]
    if event == "session_start":
        fields["source"] = data.get("source", "startup")
    if event in ("stop", "subagent_stop"):
        fields["stop_hook_active"] = bool(data.get("continues_so_far"))
    return fields


def matches(matcher: Optional[str], event: str, data: Dict[str, Any]) -> bool:
    """Whether a Claude Code hook `matcher` selects this event (no matcher: always)."""
    if not matcher or matcher == "*":
        return True
    if "tool_name" in data:
        subject = claude_tool(str(data["tool_name"]))
    elif event == "session_start":
        subject = str(data.get("source", "startup"))
    else:
        return True
    try:
        return re.fullmatch(matcher, subject) is not None
    except re.error:
        return matcher == subject


def _python_command(command: str) -> str:
    """`python3 ...` where only `python` (or `py`) exists, as on most Windows machines."""
    if not command.startswith("python3 ") or sys.platform != "win32":
        return command
    found = shutil.which("python3")
    if found and "WindowsApps" not in found:
        return command
    for name in ("python", "py"):
        other = shutil.which(name)
        if other and "WindowsApps" not in other:
            return name + command[len("python3") :]
    return f'"{sys.executable}"' + command[len("python3") :]


def expand_root(value: Any, root: Path) -> Any:
    """Replace ${CLAUDE_PLUGIN_ROOT} and ${PLUGIN_DIR} in strings, lists and mappings."""
    if isinstance(value, str):
        return value.replace("${CLAUDE_PLUGIN_ROOT}", str(root)).replace("${PLUGIN_DIR}", str(root))
    if isinstance(value, list):
        return [expand_root(v, root) for v in value]
    if isinstance(value, dict):
        return {k: expand_root(v, root) for k, v in value.items()}
    return value


def read_hooks_json(path: Path, root: Path) -> Dict[str, List[Dict[str, Any]]]:
    """
    A Claude Code hooks.json as a Joshu `hooks:` mapping:
    {joshu_event: [{command, timeout, matcher}]}. Unknown events are skipped.
    """
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    hooks: Dict[str, List[Dict[str, Any]]] = {}
    for event, groups in (data.get("hooks") or {}).items():
        joshu_event = JOSHU_EVENTS.get(event)
        if joshu_event is None or not isinstance(groups, list):
            continue
        for group in groups:
            if not isinstance(group, dict):
                continue
            for hook in group.get("hooks") or []:
                if not isinstance(hook, dict) or hook.get("type", "command") != "command":
                    continue
                command = str(expand_root(hook.get("command") or "", root)).strip()
                if not command:
                    continue
                entry: Dict[str, Any] = {"command": _python_command(command)}
                if isinstance(hook.get("timeout"), int):
                    entry["timeout"] = hook["timeout"]
                if group.get("matcher"):
                    entry["matcher"] = str(group["matcher"])
                hooks.setdefault(joshu_event, []).append(entry)
    return hooks


def read_mcp_json(path: Path, root: Path) -> Dict[str, Any]:
    """MCP servers from a Claude Code .mcp.json ({"mcpServers": {...}})."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    servers = data.get("mcpServers", data) if isinstance(data, dict) else {}
    return {
        name: expand_root(server, root)
        for name, server in servers.items()
        if isinstance(server, dict)
    }


def response_fields(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    A Claude Code hook's JSON output in Joshu's terms: additional_context,
    action ("block") and message.
    """
    out: Dict[str, Any] = {}
    specific = (
        data.get("hookSpecificOutput") if isinstance(data.get("hookSpecificOutput"), dict) else {}
    )
    context = specific.get("additionalContext") or data.get("additionalContext")
    if context:
        out["additional_context"] = str(context)
    decision = str(data.get("decision") or specific.get("permissionDecision") or "").lower()
    if decision in ("block", "deny") or data.get("continue") is False:
        out["action"] = "block"
        reason = (
            data.get("reason") or specific.get("permissionDecisionReason") or data.get("stopReason")
        )
        if reason:
            out["message"] = str(reason)
    if data.get("systemMessage") and "message" not in out:
        out["message"] = str(data["systemMessage"])
    return out
