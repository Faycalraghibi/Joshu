"""Terminal rendering and approval prompts for the agent loop."""

from __future__ import annotations

import json
import sys
from typing import Any, Dict, Optional

from rich.console import Console
from rich.markup import escape
from rich.panel import Panel
from rich.syntax import Syntax

from joshu.core.agent import Agent, AgentEvents, AgentResponse
from joshu.core.config import get_config_manager
from joshu.core.llm_client import AssistantTurn
from joshu.core.permissions import (
    ApprovalChoice,
    ApprovalRequest,
    PermissionManager,
    PermissionMode,
)

# Argument shown next to the tool name, per tool
_SUMMARY_KEYS = {
    "read_file": "path",
    "write_file": "path",
    "replace": "path",
    "list_directory": "path",
    "glob": "pattern",
    "search_file_content": "pattern",
    "run_shell_command": "command",
    "web_search": "query",
    "web_fetch": "url",
    "task": "description",
}


class ConsoleAgentUI(AgentEvents):
    """Streams the agent's text, shows tool calls, and asks for approval."""

    def __init__(self, console: Optional[Console] = None, quiet: bool = False) -> None:
        """
        Args:
            console: Rich console to print to
            quiet: Show nothing but approval prompts (headless --print mode)
        """
        self.console = console or Console()
        self.quiet = quiet
        self._mid_line = False
        self._streamed = False  # text arrived through on_text this turn

    # ---------------------------------------------------------------- events

    def on_text(self, delta: str) -> None:
        if self.quiet:
            return
        sys.stdout.write(delta)
        sys.stdout.flush()
        self._mid_line = not delta.endswith("\n")
        self._streamed = True

    def on_turn_end(self, turn: AssistantTurn) -> None:
        # A client that doesn't stream delivers the whole text at the end
        if not self.quiet and not self._streamed and turn.content:
            sys.stdout.write(turn.content)
            self._mid_line = not turn.content.endswith("\n")
        self._streamed = False
        self._end_line()

    def on_tool_start(self, name: str, arguments: Dict[str, Any]) -> None:
        if self.quiet:
            return
        self._end_line()
        summary = escape(summarize_arguments(name.split(" › ")[-1], arguments))
        self.console.print(f"[bold cyan]●[/bold cyan] [bold]{escape(name)}[/bold]({summary})")

    def on_tool_end(self, name: str, output: str, success: bool) -> None:
        if self.quiet:
            return
        first_line = escape(_first_line(output, 120))
        if success:
            line_count = output.count("\n") + 1
            summarized = _json_summary(output) is not None
            more = (
                f" [dim](+{line_count - 1} lines)[/dim]"
                if line_count > 1 and not summarized
                else ""
            )
            self.console.print(f"  [dim]└ {first_line}[/dim]{more}")
            if "now has problems. Fix them" in output:
                self.console.print(
                    "  [yellow]└ problems found after the edit; the agent will fix them[/yellow]"
                )
        else:
            self.console.print(f"  [red]└ {escape(name)}: {first_line}[/red]")

    def on_compact(self, tokens_before: int, tokens_after: int) -> None:
        if self.quiet:
            return
        self._end_line()
        self.console.print(
            f"[dim]Context compacted: ~{tokens_before:,} → ~{tokens_after:,} tokens[/dim]"
        )

    # -------------------------------------------------------------- approval

    def approve(self, request: ApprovalRequest) -> ApprovalChoice:
        """Show what the tool will do and ask the user."""
        self._end_line()
        title = f"{request.tool_name} wants to run"
        if request.preview.startswith(("--- ", "diff ")) or "\n@@ " in request.preview:
            body: Any = Syntax(request.preview, "diff", word_wrap=True)
        else:
            body = escape(request.preview)
        self.console.print(Panel(body, title=escape(title), border_style="yellow"))

        if request.warning:
            self.console.print(f"[bold red]Warning:[/bold red] {escape(request.warning)}")
            options = "[y]es / [n]o"
        else:
            options = "[y]es / [a]lways this session / [n]o"

        while True:
            try:
                answer = self.console.input(f"Allow? {escape(options)}: ").strip().lower()
            except (EOFError, KeyboardInterrupt):
                self.console.print()
                return ApprovalChoice.NO
            if answer in ("y", "yes"):
                return ApprovalChoice.YES
            if answer in ("a", "always") and not request.warning:
                return ApprovalChoice.ALWAYS
            if answer in ("", "n", "no"):
                return ApprovalChoice.NO

    # --------------------------------------------------------------- helpers

    def print_footer(self, response: AgentResponse) -> None:
        """Dim line with turn and token counts."""
        if self.quiet:
            return
        meta = response.metadata
        usage = meta.get("usage", {})
        tokens = usage.get("prompt_tokens", 0) + usage.get("completion_tokens", 0)
        parts = [f"{meta.get('tool_calls', 0)} tool calls"]
        if tokens:
            parts.append(f"{tokens:,} tokens this session")
        if meta.get("cost_usd") is not None:
            parts.append(f"${meta['cost_usd']:.4f}")
        if meta.get("model"):
            parts.append(str(meta["model"]))
        self.console.print(f"[dim]{' · '.join(parts)}[/dim]")

    def _end_line(self) -> None:
        if self._mid_line:
            sys.stdout.write("\n")
            sys.stdout.flush()
            self._mid_line = False


def summarize_arguments(tool_name: str, arguments: Dict[str, Any], limit: int = 80) -> str:
    """One-line summary of a tool call's arguments."""
    key = _SUMMARY_KEYS.get(tool_name)
    if key and key in arguments:
        value = str(arguments[key])
    elif arguments:
        value = json.dumps(arguments, ensure_ascii=False)
    else:
        value = ""
    value = value.replace("\n", " ")
    return value if len(value) <= limit else value[: limit - 3] + "..."


def _first_line(text: str, limit: int) -> str:
    line = _json_summary(text) or (
        text.strip().split("\n", 1)[0] if text.strip() else "(no output)"
    )
    return line if len(line) <= limit else line[: limit - 3] + "..."


def _json_summary(text: str) -> Optional[str]:
    """Short description of a JSON tool result, e.g. "12 matches" or its error."""
    text = text.lstrip()
    if not text.startswith("{"):
        return None
    try:
        # Text may follow the JSON object (e.g. diagnostics after an edit)
        data, _ = json.JSONDecoder().raw_decode(text)
    except ValueError:
        return None
    if not isinstance(data, dict):
        return None
    if data.get("error"):
        return str(data["error"])
    if data.get("message"):
        return str(data["message"])
    for key in ("matches", "files", "entries", "results", "todos"):
        if isinstance(data.get(key), list):
            return f"{len(data[key])} {key}"
    if "exit_code" in data:
        return f"exit code {data['exit_code']}"
    if "total_lines" in data:
        return f"{data['total_lines']} lines"
    return None


def create_console_agent(
    model: Optional[str] = None,
    mode: Optional[PermissionMode] = None,
    provider: Optional[str] = None,
    sandbox: bool = False,
    interactive: bool = True,
    console: Optional[Console] = None,
    quiet: bool = False,
) -> tuple[Agent, ConsoleAgentUI]:
    """
    Build an agent wired to the terminal.

    Args:
        mode: Permission mode (defaults to the configured one)
        interactive: Ask the user for approvals; False denies anything that
            needs approval (for headless runs)

    Raises:
        LLMError: if no model endpoint is configured
    """
    from joshu.hooks import configure_hooks_from_settings

    config = get_config_manager()
    ui = ConsoleAgentUI(console, quiet=quiet)
    for problem in configure_hooks_from_settings(config.get("hooks") or {}):
        ui.console.print(f"[yellow]Hook configuration: {problem}[/yellow]")
    if mode is None:
        mode = PermissionMode.from_string(config.get("permission_mode", "default"))
    permissions = PermissionManager(
        mode, approver=ui.approve if interactive else None, sandbox=sandbox
    )
    agent = Agent(
        permissions=permissions,
        events=ui,
        model=model,
        provider=provider,
        stream=not quiet,
        persist=config.get("save_sessions", True),
    )
    return agent, ui
