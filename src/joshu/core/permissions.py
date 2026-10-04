"""
Permission gate between the agent loop and tool execution.

Every tool call the model requests goes through PermissionManager.check() before
it runs. Read-only tools run freely; edits and shell commands ask the user
(unless the mode or a session rule allows them); plan mode denies anything that
changes state.
"""

from __future__ import annotations

import fnmatch
import json
import logging
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set

from joshu.core.safety import assess_command_safety

logger = logging.getLogger(__name__)

# Tools that never change files or run commands
READ_ONLY_TOOLS: Set[str] = {
    "read_file",
    "list_directory",
    "glob",
    "search_file_content",
    "web_search",
    "write_todos",
    "task",
}

EDIT_TOOLS: Set[str] = {"replace", "write_file"}

SHELL_TOOL = "run_shell_command"


class PermissionMode(str, Enum):
    """How much the agent may do without asking."""

    DEFAULT = "default"  # ask before edits, shell and other approval-required tools
    ACCEPT_EDITS = "accept_edits"  # file edits run freely; shell still asks
    PLAN = "plan"  # read-only: anything that changes state is denied
    BYPASS = "bypass"  # everything runs, except commands flagged unsafe

    @classmethod
    def from_string(cls, value: str) -> "PermissionMode":
        normalized = value.strip().lower().replace("-", "_")
        for mode in cls:
            if mode.value == normalized:
                return mode
        valid = ", ".join(m.value for m in cls)
        raise ValueError(f"Unknown permission mode '{value}'. Valid modes: {valid}")


class ApprovalChoice(str, Enum):
    """User's answer to an approval prompt."""

    YES = "yes"
    ALWAYS = "always"  # yes, and stop asking for this tool (or command) this session
    NO = "no"


@dataclass
class ApprovalRequest:
    """What the user is asked to approve."""

    tool_name: str
    arguments: Dict[str, Any]
    preview: str  # diff, command, or argument summary
    warning: Optional[str] = None  # set when the safety check flagged the call
    # What the user said to do instead when declining (sent to the model)
    feedback: Optional[str] = None


@dataclass
class PermissionDecision:
    """Outcome of a permission check."""

    allowed: bool
    reason: str = ""


Approver = Callable[[ApprovalRequest], ApprovalChoice]


# Argument a rule's pattern is matched against, per tool
_RULE_SUBJECT = {
    SHELL_TOOL: "command",
    "read_file": "path",
    "write_file": "path",
    "replace": "path",
    "list_directory": "path",
    "web_fetch": "url",
}
_RULE_PATTERN = re.compile(r"^\s*([A-Za-z0-9_.-]+)\s*(?:\((.*)\))?\s*$")


@dataclass
class PermissionRule:
    """`tool` or `tool(pattern)`; the pattern is a glob over the tool's main argument."""

    tool: str
    pattern: Optional[str] = None

    @classmethod
    def parse(cls, text: str) -> "PermissionRule":
        match = _RULE_PATTERN.match(text or "")
        if not match:
            raise ValueError(f"Invalid permission rule '{text}': use tool or tool(pattern)")
        pattern = match.group(2)
        return cls(match.group(1), pattern.strip() if pattern is not None else None)

    def matches(self, tool_name: str, arguments: Dict[str, Any]) -> bool:
        if tool_name != self.tool:
            return False
        if self.pattern is None:
            return True
        key = _RULE_SUBJECT.get(tool_name)
        subject = str(arguments.get(key, "")) if key else json.dumps(arguments, sort_keys=True)
        if tool_name in ("read_file", "write_file", "replace", "list_directory"):
            subject = subject.replace("\\", "/")
        return fnmatch.fnmatchcase(subject, self.pattern)

    def __str__(self) -> str:
        return self.tool if self.pattern is None else f"{self.tool}({self.pattern})"


@dataclass
class PermissionRules:
    """Persistent allow/deny rules (the `permissions` setting)."""

    allow: List[PermissionRule] = field(default_factory=list)
    deny: List[PermissionRule] = field(default_factory=list)

    @classmethod
    def from_config(cls, data: Optional[Dict[str, Any]]) -> "PermissionRules":
        data = data or {}
        rules = cls()
        for name in ("allow", "deny"):
            for text in data.get(name) or []:
                try:
                    getattr(rules, name).append(PermissionRule.parse(str(text)))
                except ValueError as e:
                    logger.warning(str(e))
        return rules

    def denies(self, tool_name: str, arguments: Dict[str, Any]) -> Optional[PermissionRule]:
        return next((r for r in self.deny if r.matches(tool_name, arguments)), None)

    def allows(self, tool_name: str, arguments: Dict[str, Any]) -> Optional[PermissionRule]:
        return next((r for r in self.allow if r.matches(tool_name, arguments)), None)


class PermissionManager:
    """Decides whether a tool call may run."""

    def __init__(
        self,
        mode: PermissionMode = PermissionMode.DEFAULT,
        approver: Optional[Approver] = None,
        sandbox: bool = False,
        sandboxed_shell: bool = False,
        rules: Optional[PermissionRules] = None,
    ) -> None:
        """
        Args:
            mode: Permission mode
            approver: Callback that asks the user; None means non-interactive
                (anything that needs approval is denied)
            sandbox: Passed to the shell safety check (blocks all destructive commands)
            sandboxed_shell: Shell commands run in an OS sandbox (joshu.core.sandbox),
                so they don't need approval; commands flagged unsafe still do
            rules: Persistent allow/deny rules; defaults to the `permissions`
                setting
        """
        self.mode = mode
        self.approver = approver
        self.sandbox = sandbox
        self.sandboxed_shell = sandboxed_shell
        if rules is None:
            from joshu.core.config import get_config_manager

            rules = PermissionRules.from_config(get_config_manager().get("permissions"))
        self.rules = rules
        self._always_allowed_tools: Set[str] = set()
        self._always_allowed_commands: Set[str] = set()

    def check(
        self, tool_name: str, arguments: Dict[str, Any], requires_approval: bool
    ) -> PermissionDecision:
        """Check (and if needed ask about) one tool call."""
        denied_by = self.rules.denies(tool_name, arguments)
        if denied_by is not None:
            return PermissionDecision(False, f"Blocked by the permission rule '{denied_by}'.")

        # Protected files (.env, keys, ...) always need an explicit yes, in every mode
        from joshu.core.secrets import sensitive_reason

        secret = sensitive_reason(tool_name, arguments)
        if secret is not None:
            if self.rules.allows(tool_name, arguments) is not None:
                return PermissionDecision(True)
            return self._ask(tool_name, arguments, secret, allow_always=False)

        warning = None
        if tool_name == SHELL_TOOL:
            command = str(arguments.get("command", ""))
            report = assess_command_safety(command, self.sandbox)
            if not report.safe:
                warning = "; ".join(report.reasons) or f"flagged as {report.danger_level}"

        if self.mode == PermissionMode.PLAN:
            if tool_name in READ_ONLY_TOOLS or (
                not requires_approval and tool_name not in EDIT_TOOLS and tool_name != SHELL_TOOL
            ):
                return PermissionDecision(True)
            return PermissionDecision(
                False,
                "Plan mode is read-only: this tool is not allowed. "
                "Describe the change in your plan instead.",
            )

        # Unsafe shell commands always need an explicit yes, whatever the mode
        if warning is not None:
            return self._ask(tool_name, arguments, warning, allow_always=False)

        if self.mode == PermissionMode.BYPASS:
            return PermissionDecision(True)

        if tool_name == SHELL_TOOL and self.sandboxed_shell:
            return PermissionDecision(True)

        if self.mode == PermissionMode.ACCEPT_EDITS and tool_name in EDIT_TOOLS:
            return PermissionDecision(True)

        if not requires_approval:
            return PermissionDecision(True)

        if self.rules.allows(tool_name, arguments) is not None:
            return PermissionDecision(True)

        if self._is_always_allowed(tool_name, arguments):
            return PermissionDecision(True)

        return self._ask(tool_name, arguments, None, allow_always=True)

    def _ask(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        warning: Optional[str],
        allow_always: bool,
    ) -> PermissionDecision:
        if self.approver is None:
            reason = (
                f"'{tool_name}' requires approval and no one is available to approve it. "
                "Re-run with --permission-mode accept_edits or bypass to allow it."
            )
            if warning:
                reason = f"Command blocked by safety check: {warning}"
            return PermissionDecision(False, reason)

        request = ApprovalRequest(
            tool_name=tool_name,
            arguments=arguments,
            preview=build_preview(tool_name, arguments),
            warning=warning,
        )
        from joshu.hooks.dispatcher import dispatch_notification

        dispatch_notification(
            "", f"Joshu needs your approval to run {tool_name}", {"tool_name": tool_name}
        )
        choice = self.approver(request)

        if choice == ApprovalChoice.NO:
            reason = "The user denied this tool call."
            if request.feedback:
                reason += f" They said: {request.feedback}"
            return PermissionDecision(False, reason)

        if choice == ApprovalChoice.ALWAYS and allow_always:
            self._remember(tool_name, arguments)

        return PermissionDecision(True)

    def _remember(self, tool_name: str, arguments: Dict[str, Any]) -> None:
        if tool_name == SHELL_TOOL:
            key = command_key(str(arguments.get("command", "")))
            if key:
                self._always_allowed_commands.add(key)
        else:
            self._always_allowed_tools.add(tool_name)

    def _is_always_allowed(self, tool_name: str, arguments: Dict[str, Any]) -> bool:
        if tool_name == SHELL_TOOL:
            key = command_key(str(arguments.get("command", "")))
            return bool(key) and key in self._always_allowed_commands
        return tool_name in self._always_allowed_tools


def command_key(command: str) -> str:
    """
    Key used for "always allow" on shell commands: the program plus its
    subcommand, e.g. "git status", "npm test", "pytest".

    Commands chained with ;, &&, || or | never get a key, so approving
    "git status" can't silently approve "git status && rm -rf build".
    """
    if any(sep in command for sep in (";", "&", "|", "`", "$(", ">", "<", "\n")):
        return ""
    tokens = command.split()
    if not tokens:
        return ""
    if len(tokens) > 1 and not tokens[1].startswith("-"):
        return f"{tokens[0]} {tokens[1]}"
    return tokens[0]


def build_preview(tool_name: str, arguments: Dict[str, Any]) -> str:
    """Human-readable preview of what a tool call will do."""
    try:
        if tool_name == "replace":
            return _replace_preview(arguments)
        if tool_name == "write_file":
            return _write_preview(arguments)
        if tool_name == SHELL_TOOL:
            preview = f"$ {arguments.get('command', '')}"
            if arguments.get("working_directory"):
                preview += f"\n(in {arguments['working_directory']})"
            return preview
    except Exception as e:
        logger.debug(f"Preview failed for {tool_name}: {e}")

    lines = [f"{key}: {_short(value)}" for key, value in arguments.items()]
    return "\n".join(lines) if lines else "(no arguments)"


def _replace_preview(arguments: Dict[str, Any]) -> str:
    from joshu.tools.filesystem_tools import generate_diff, resolve_path

    path = str(arguments.get("path", ""))
    resolved = resolve_path(path)
    content = resolved.read_text(encoding="utf-8")
    old = str(arguments.get("old_string", ""))
    new = str(arguments.get("new_string", ""))
    if old not in content:
        return f"{path}: old_string not found (the tool will fail)"
    count = -1 if arguments.get("all_occurrences") else 1
    return generate_diff(content, content.replace(old, new, count), path) or "(no change)"


def _write_preview(arguments: Dict[str, Any]) -> str:
    from joshu.tools.filesystem_tools import generate_diff, resolve_path

    path = str(arguments.get("path", ""))
    resolved = resolve_path(path)
    new = str(arguments.get("content", ""))
    if resolved.exists():
        old = resolved.read_text(encoding="utf-8")
        return generate_diff(old, new, path) or "(no change)"
    line_count = new.count("\n") + (1 if new and not new.endswith("\n") else 0)
    head = "\n".join(f"+{line}" for line in new.splitlines()[:40])
    more = "\n..." if line_count > 40 else ""
    return f"New file {path} ({line_count} lines)\n{head}{more}"


def _short(value: Any, limit: int = 200) -> str:
    text = value if isinstance(value, str) else repr(value)
    return text if len(text) <= limit else text[:limit] + "..."
