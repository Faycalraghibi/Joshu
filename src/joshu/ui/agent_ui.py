"""Terminal rendering and approval prompts for the agent loop."""

from __future__ import annotations

import functools
import json
import sys
import threading
import time
from typing import Any, Dict, List, Optional, Tuple

from rich.console import Console, Group
from rich.live import Live
from rich.markdown import Markdown
from rich.markup import escape
from rich.padding import Padding
from rich.panel import Panel
from rich.segment import Segment
from rich.syntax import Syntax
from rich.table import Table
from rich.text import Text

from joshu.core.agent import Agent, AgentEvents, AgentResponse
from joshu.core.config import get_config_manager
from joshu.core.llm_client import AssistantTurn
from joshu.core.permissions import (
    ApprovalChoice,
    ApprovalRequest,
    PermissionManager,
    PermissionMode,
)
from joshu.ui.theme import GLYPH, SPINNER_FRAMES, current_theme, style

# Argument shown next to the tool name, per tool
_SUMMARY_KEYS: Dict[str, Optional[str]] = {
    "read_file": "path",
    "write_file": "path",
    "replace": "path",
    "multi_edit": "path",
    "notebook_edit": "path",
    "code_nav": "symbol",
    "list_directory": "path",
    "glob": "pattern",
    "search_file_content": "pattern",
    "run_shell_command": "command",
    "web_search": "query",
    "web_fetch": "url",
    "task": "description",
    "skill": "name",
    "memory": "name",
    "write_todos": None,
}

# How tools are named on screen
TOOL_LABELS = {
    "read_file": "Read",
    "write_file": "Write",
    "replace": "Update",
    "multi_edit": "Update",
    "notebook_edit": "Edit Notebook",
    "code_nav": "Navigate",
    "run_shell_command": "Bash",
    "search_file_content": "Search",
    "glob": "Glob",
    "list_directory": "List",
    "web_search": "Web Search",
    "web_fetch": "Fetch",
    "task": "Task",
    "write_todos": "Update Todos",
    "memory": "Memory",
    "save_memory": "Memory",
    "skill": "Skill",
}

RESULT = "  ⎿  "
RESULT_INDENT = "     "
MAX_DIFF_LINES = 24
MAX_OUTPUT_LINES = 4


def _s(role: str, *extra: str) -> str:
    """Rich style for a theme color role (accent, error, ...)."""
    return style(getattr(current_theme(), role), *extra)


# What the working indicator says while a tool runs
_ACTIVITY = {
    "read_file": ("Reading", "path"),
    "write_file": ("Writing", "path"),
    "replace": ("Editing", "path"),
    "run_shell_command": ("Running", "command"),
    "search_file_content": ("Searching for", "pattern"),
    "glob": ("Finding", "pattern"),
    "list_directory": ("Listing", "path"),
    "web_search": ("Searching the web for", "query"),
    "web_fetch": ("Fetching", "url"),
    "task": ("Delegating:", "description"),
    "skill": ("Loading skill", "name"),
    "memory": ("Updating memory", None),
    "write_todos": ("Updating todos", None),
}


def activity_label(tool: str, arguments: Dict[str, Any]) -> str:
    verb, key = _ACTIVITY.get(tool, ("Running " + TOOL_LABELS.get(tool, tool), None))
    if key and arguments.get(key):
        value = " ".join(str(arguments[key]).split())
        value = value if len(value) <= 50 else value[:47] + "..."
        return f"{verb} {value}"
    return verb


class _Working:
    """Working indicator with elapsed time, re-rendered by rich.live."""

    def __init__(self, label: str = "Thinking") -> None:
        self.started = time.monotonic()
        self.label = label
        self.chars = 0  # streamed text so far, for the output-token estimate

    def __rich_console__(self, console, options):
        elapsed = time.monotonic() - self.started
        frame = SPINNER_FRAMES[int(elapsed * 6) % len(SPINNER_FRAMES)]
        details = [_elapsed(elapsed)]
        if self.chars:
            details.append(f"↓ {_short(max(1, self.chars // 4))} tokens")
        details.append("esc to interrupt")
        yield Text.assemble(
            (f"{frame} ", _s("accent", "bold")),
            (f"{self.label}… ", _s("accent")),
            (f"({' · '.join(details)})", "dim"),
        )


class _Trimmed:
    """A renderable without blank lines at its edges.

    rich's Markdown starts a list or code block with an empty line, so a reply
    printed block by block would otherwise get uneven spacing.
    """

    def __init__(self, renderable: Any) -> None:
        self.renderable = renderable

    def __rich_console__(self, console, options):
        lines = console.render_lines(self.renderable, options, pad=False)

        def blank(line) -> bool:
            return not "".join(segment.text for segment in line).strip()

        while lines and blank(lines[0]):
            lines.pop(0)
        while lines and blank(lines[-1]):
            lines.pop()
        for line in lines:
            yield from line
            yield Segment.line()


class _StreamView:
    """The reply still being written, above the working indicator."""

    def __init__(self, ui: "ConsoleAgentUI", working: _Working) -> None:
        self.ui = ui
        self.working = working

    def __rich_console__(self, console, options):
        tail = self.ui._pending.strip()
        if tail:
            yield self.ui._message_block(tail, first=not self.ui._reply_started)
            yield Text()
        yield self.working


def _elapsed(seconds: float) -> str:
    seconds = int(seconds)
    return f"{seconds // 60}m {seconds % 60}s" if seconds >= 60 else f"{seconds}s"


def split_complete_blocks(text: str) -> "tuple[str, str]":
    """Split streamed Markdown into finished blocks and the block still being written.

    A block is finished at a blank line outside a code fence, so a printed
    block never changes once later text arrives.
    """
    fence: Optional[str] = None
    cut = 0
    position = 0
    lines = text.split("\n")
    for index, line in enumerate(lines):
        position += len(line) + 1
        if index == len(lines) - 1:
            break  # the last line may still be growing
        stripped = line.strip()
        marker = stripped[:3]
        if marker in ("```", "~~~"):
            if fence is None:
                fence = marker
            elif marker == fence and stripped.strip("`~") == "":
                fence = None
            continue
        if fence is None and not stripped:
            cut = position
    return text[:cut], text[cut:]


def _locked(method):
    """Serialize UI updates: sub-agents running in parallel report from worker threads."""

    @functools.wraps(method)
    def wrapper(self, *args, **kwargs):
        with self._lock:
            return method(self, *args, **kwargs)

    return wrapper


class ConsoleAgentUI(AgentEvents):
    """Shows the agent's replies and tool calls, and asks for approval."""

    def __init__(self, console: Optional[Console] = None, quiet: bool = False) -> None:
        """
        Args:
            console: Rich console to print to
            quiet: Show nothing but approval prompts (headless --print mode)
        """
        self.console = console or Console()
        self.quiet = quiet
        # On a terminal, replies are rendered as Markdown while they stream;
        # otherwise text is written as it arrives
        self.rich_mode = self.console.is_terminal and not quiet
        self._mid_line = False
        self._streamed = False  # text arrived through on_text this turn
        self._buffer: List[str] = []
        # Live reply: finished Markdown blocks are printed as they complete and
        # only the block being written is redrawn
        self._pending = ""
        self._reply_started = False
        self._working: Optional[_Working] = None
        self._live: Optional[Live] = None
        self._arguments: Dict[str, Any] = {}
        self._lock = threading.RLock()
        # Tool output cut short this request, for Ctrl+O: (call, full text)
        self.expandable: List[Tuple[str, str]] = []
        self.verbose = False  # Ctrl+O while the agent works: show output in full
        self._call = ""
        self._todo = ""  # task in progress, shown in the working line
        self._request_started: Optional[float] = None

    def begin_request(self) -> None:
        """A new request starts: forget the previous one's output, start its clock."""
        with self._lock:
            self.expandable = []
            self._request_started = time.monotonic()

    # ---------------------------------------------------------------- events

    @_locked
    def on_model_start(self) -> None:
        if self.rich_mode:
            self._start_spinner()

    @_locked
    def on_text(self, delta: str) -> None:
        if self.quiet:
            return
        if self.rich_mode:
            self._buffer.append(delta)
            self._stream(delta)
            return
        sys.stdout.write(delta)
        sys.stdout.flush()
        self._mid_line = not delta.endswith("\n")
        self._streamed = True

    @_locked
    def on_turn_end(self, turn: AssistantTurn) -> None:
        if self.quiet:
            return
        if self.rich_mode:
            streamed = bool(self._buffer)
            self._buffer = []
            if streamed:
                self._stop_spinner()  # prints the last block
            else:
                # A client that doesn't stream delivers the whole text at the end
                self._stop_spinner()
                if (turn.content or "").strip():
                    self._print_message(turn.content or "")
            self._reply_started = False
            return
        # A client that doesn't stream delivers the whole text at the end
        if not self._streamed and turn.content:
            sys.stdout.write(turn.content)
            self._mid_line = not turn.content.endswith("\n")
        self._streamed = False
        self._end_line()

    @_locked
    def on_tool_start(self, name: str, arguments: Dict[str, Any]) -> None:
        if self.quiet:
            return
        self._stop_spinner()
        self._end_line()
        self._arguments = arguments
        prefix, _, tool = name.rpartition(" › ")
        label = TOOL_LABELS.get(tool, tool)
        if prefix:
            label = f"{prefix} › {label}"
        plain = summarize_arguments(tool, arguments)
        self._call = f"{label}({plain})" if plain else label
        summary = escape(plain)
        args = f"({summary})" if summary else ""
        self.console.print()
        # One line: cut with … at the edge rather than wrapping the label away from ●
        self.console.print(
            f"[{_s('accent')}]●[/] [bold]{escape(label)}[/bold]{args}",
            no_wrap=True,
            overflow="ellipsis",
            highlight=False,
        )
        self._start_spinner(activity_label(tool, arguments))

    @_locked
    def on_tool_end(self, name: str, output: str, success: bool) -> None:
        if self.quiet:
            return
        self._stop_spinner()
        tool = name.rpartition(" › ")[2]
        if not success:
            hint = self._fold(output)
            self.console.print(
                f"[{_s('error')}]{RESULT}{escape(_first_line(output, 160))}[/]{hint}",
                highlight=False,
            )
            return
        renderer = {
            "replace": self._show_edit,
            "multi_edit": self._show_edit,
            "write_file": self._show_write,
            "run_shell_command": self._show_shell,
            "write_todos": self._show_todos,
            "read_file": self._show_read,
        }.get(tool)
        if renderer is None or not renderer(output):
            hint = self._fold(output)
            self._result_line(escape(_first_line(output, 160)) + hint)
        if "now has problems. Fix them" in output:
            self.console.print(
                f"[{_s('warning')}]{RESULT_INDENT}problems found after the edit; "
                "the agent will fix them[/]"
            )

    @_locked
    def on_compact(self, tokens_before: int, tokens_after: int) -> None:
        if self.quiet:
            return
        self._stop_spinner()
        self._end_line()
        self.console.print(
            f"[dim]{GLYPH} Context compacted: ~{tokens_before:,} → ~{tokens_after:,} tokens[/dim]"
        )

    @_locked
    def on_parallel_start(self, count: int) -> None:
        if self.rich_mode and count > 1:
            self._stop_spinner()
            self._start_spinner(f"Running {count} tools in parallel")

    @_locked
    def on_context_cleared(self, items: int, tokens_freed: int) -> None:
        if self.quiet:
            return
        self._stop_spinner()
        self._end_line()
        self.console.print(
            f"[dim]{GLYPH} Cleared {items} old tool result{'s' if items != 1 else ''} "
            f"(~{tokens_freed:,} tokens); the agent can re-run a tool to see one again[/dim]"
        )

    # ------------------------------------------------------- tool results

    def _result_line(self, markup: str) -> None:
        self.console.print(f"[dim]{RESULT}[/dim]{markup}", highlight=False)

    def _show_read(self, output: str) -> bool:
        data = _json(output)
        if not data or "total_lines" not in data:
            return False
        self._result_line(f"Read [bold]{data['total_lines']}[/bold] lines")
        return True

    def _show_write(self, output: str) -> bool:
        content = str(self._arguments.get("content") or "")
        lines = content.count("\n") + (1 if content and not content.endswith("\n") else 0)
        path = escape(_relative(str(self._arguments.get("path", ""))))
        self._result_line(f"Wrote [bold]{lines}[/bold] lines to [bold]{path}[/bold]")
        return True

    def _show_edit(self, output: str) -> bool:
        data = _json(output)
        diff = str((data or {}).get("diff") or "")
        if not diff:
            return False
        added = sum(
            1 for line in diff.splitlines() if line.startswith("+") and not line.startswith("+++")
        )
        removed = sum(
            1 for line in diff.splitlines() if line.startswith("-") and not line.startswith("---")
        )
        path = escape(_relative(str(self._arguments.get("path", ""))))
        self._result_line(
            f"Updated [bold]{path}[/bold] with [bold]{added}[/bold] "
            f"addition{'s' if added != 1 else ''} and [bold]{removed}[/bold] "
            f"removal{'s' if removed != 1 else ''}"
        )
        self.console.print(Padding(render_diff(diff, MAX_DIFF_LINES), (0, 0, 0, 5)))
        return True

    def _show_shell(self, output: str) -> bool:
        data = _json(output)
        if not data:
            return False
        text = "\n".join(
            part for part in (str(data.get("stdout") or ""), str(data.get("stderr") or "")) if part
        ).rstrip()
        lines = text.splitlines()
        if not lines:
            code = data.get("exit_code")
            self._result_line("(no output)" if code in (0, None) else f"exit code {code}")
            return True
        failed = data.get("exit_code") not in (0, None)
        limit = len(lines) if self.verbose else MAX_OUTPUT_LINES
        if len(lines) > MAX_OUTPUT_LINES:
            self.expandable.append((self._call, text))
        for index, line in enumerate(lines[:limit]):
            lead = RESULT if index == 0 else RESULT_INDENT
            shown = escape(line[:200])
            self.console.print(
                f"[dim]{lead}[/dim]" + (f"[{_s('error')}]{shown}[/]" if failed else shown),
                highlight=False,
            )
        if len(lines) > limit:
            self.console.print(
                f"[dim]{RESULT_INDENT}… +{len(lines) - limit} lines (ctrl+o to expand)[/dim]"
            )
        return True

    def _show_todos(self, output: str) -> bool:
        todos = self._arguments.get("todos")
        if not isinstance(todos, list) or not todos:
            return False
        self._todo = next(
            (
                str(todo.get("description", ""))
                for todo in todos
                if isinstance(todo, dict) and todo.get("status") == "in_progress"
            ),
            "",
        )
        for index, todo in enumerate(todos):
            if not isinstance(todo, dict):
                continue
            status = todo.get("status", "pending")
            text = escape(str(todo.get("description", "")))
            if status == "completed":
                item = f"[dim]☒ [strike]{text}[/strike][/dim]"
            elif status == "in_progress":
                item = f"[bold]☐ {text}[/bold]"
            elif status == "cancelled":
                item = f"[dim]☒ [strike]{text}[/strike] (cancelled)[/dim]"
            else:
                item = f"☐ {text}"
            lead = RESULT if index == 0 else RESULT_INDENT
            self.console.print(f"[dim]{lead}[/dim]{item}", highlight=False)
        return True

    # -------------------------------------------------------------- approval

    @_locked
    def approve(self, request: ApprovalRequest) -> ApprovalChoice:
        """Show what the tool will do and ask the user."""
        self._stop_spinner()
        self._end_line()
        self.notify()
        tool = request.tool_name
        label = TOOL_LABELS.get(tool, tool)
        path = str(request.arguments.get("path", ""))
        if tool == "read_file":
            title, question = "Read file", f"Do you want to let Joshu read {path}?"
        elif tool in ("replace", "multi_edit", "notebook_edit"):
            title, question = "Edit file", f"Do you want to make this edit to {path}?"
        elif tool == "write_file":
            title, question = "Create file", f"Do you want to create {path}?"
        elif tool == "run_shell_command":
            title, question = "Bash command", "Do you want to run this command?"
        else:
            title, question = label, f"Do you want to allow {label}?"

        preview = request.preview
        if preview.startswith(("--- ", "diff ")) or "\n@@ " in preview:
            body: Any = render_diff(preview, 60)
        elif tool == "run_shell_command":
            body = Syntax(str(request.arguments.get("command", preview)), "bash", word_wrap=True)
        else:
            body = Text(preview)
        parts: List[Any] = [Text(title, style="bold"), Text(""), body]
        if request.warning:
            parts += [Text(""), Text.assemble(("Warning: ", _s("error", "bold")), request.warning)]
        self.console.print()
        self.console.print(Panel(Group(*parts), border_style=_s("accent"), padding=(0, 1)))

        options = [(ApprovalChoice.YES, "Yes")]
        what = _always_scope(tool, label, request.arguments)
        if not request.warning and what:
            options.append(
                (ApprovalChoice.ALWAYS, f"Yes, and don't ask again for {what} this session")
            )
        options.append((ApprovalChoice.NO, "No, and tell Joshu what to do differently (esc)"))

        from joshu.ui.key_listener import paused

        with paused():
            answer = _choose(question, options)
            if answer == ApprovalChoice.NO:
                request.feedback = _ask_feedback()
        return answer

    # --------------------------------------------------------------- helpers

    @_locked
    def print_footer(self, response: AgentResponse) -> None:
        """Dim line with this request's tokens (and how many the provider cached)."""
        if self.quiet:
            return
        self._stop_spinner()
        meta = response.metadata
        usage = meta.get("request_usage") or meta.get("usage", {})
        prompt = usage.get("prompt_tokens", 0)
        cached = usage.get("cached_tokens", 0)
        parts = []
        if prompt:
            cached_note = f" ({_short(cached)} cached)" if cached else ""
            parts.append(f"↑ {_short(prompt)} in{cached_note}")
            parts.append(f"↓ {_short(usage.get('completion_tokens', 0))} out")
        parts.append(f"{meta.get('tool_calls', 0)} tool calls")
        if meta.get("cost_usd") is not None:
            parts.append(f"${meta['cost_usd']:.4f}")
        if meta.get("model"):
            parts.append(str(meta["model"]))
        if self.expandable and self.rich_mode:
            parts.append("ctrl+o for full output")
        self.console.print(f"[dim]{' · '.join(parts)}[/dim]")
        self.notify()

    # ------------------------------------------------- expand and notify

    def _fold(self, output: str) -> str:
        """Keep output shown as one line for Ctrl+O; the hint to add, or the full text."""
        text = output.strip()
        if len(text) <= 160 and "\n" not in text:
            return ""
        self.expandable.append((self._call, text))
        if self.verbose:
            self._print_full(text)
            return ""
        return " [dim](ctrl+o to expand)[/dim]"

    def _print_full(self, text: str, limit: int = 400) -> None:
        lines = text.splitlines()
        for line in lines[:limit]:
            self.console.print(Text(RESULT_INDENT + line, style="dim"), soft_wrap=True)
        if len(lines) > limit:
            self.console.print(f"[dim]{RESULT_INDENT}… +{len(lines) - limit} lines[/dim]")

    def show_expanded(self) -> None:
        """Ctrl+O at the prompt: the last request's tool output in full."""
        if not self.expandable:
            self.console.print("[dim]Nothing was cut short in the last request.[/dim]")
            return
        for call, text in self.expandable:
            self.console.print()
            self.console.print(
                f"[{_s('accent')}]●[/] [bold]{escape(call)}[/bold]",
                highlight=False,
                no_wrap=True,
                overflow="ellipsis",
            )
            self._print_full(text)

    def toggle_verbose(self) -> None:
        """Ctrl+O while the agent works: show the rest of this request's output in full."""
        with self._lock:
            self.verbose = not self.verbose

    def notify(self) -> None:
        """Ring the bell when a request that ran a while finishes or needs an answer."""
        if self._request_started is None or not self.console.is_terminal or self.quiet:
            return
        config = get_config_manager()
        if str(config.get("notifications", "bell")).lower() != "bell":
            return
        if time.monotonic() - self._request_started < float(
            config.get("notify_after_seconds", 20) or 0
        ):
            return
        self.console.file.write("\a")
        self.console.file.flush()

    def _message_block(self, text: str, first: bool) -> Table:
        """Markdown with the reply bullet (first block) or aligned under it."""
        grid = Table.grid(padding=0)
        grid.add_column(width=2, no_wrap=True)
        grid.add_column()
        grid.add_row(Text("● " if first else "  "), _Trimmed(Markdown(text.strip())))
        return grid

    def _print_message(self, text: str) -> None:
        self.console.print()
        self.console.print(self._message_block(text, first=True))

    def _print_block(self, text: str) -> None:
        if not text.strip():
            return
        self.console.print()  # before the reply, and between blocks as Markdown would
        self.console.print(self._message_block(text, first=not self._reply_started))
        self._reply_started = True

    def _stream(self, delta: str) -> None:
        """Show streamed text: print finished blocks, redraw the one being written."""
        self._pending += delta
        done, self._pending = split_complete_blocks(self._pending)
        if done.strip():
            self._print_block(done)
        if self._live is None:
            self._start_spinner("Writing")
        if self._working is not None:
            self._working.chars += len(delta)
            self._working.label = "Writing"

    def _flush_reply(self) -> None:
        text, self._pending = self._pending, ""
        self._print_block(text)

    def _start_spinner(self, label: str = "Thinking") -> None:
        if not self.rich_mode or self._live is not None:
            return
        if label == "Thinking" and self._todo:
            label = self._todo
        self._working = _Working(label)
        self._live = Live(
            _StreamView(self, self._working),
            console=self.console,
            refresh_per_second=8,
            transient=True,
        )
        try:
            self._live.start()
        except Exception:  # never let the indicator break a request
            self._live = None

    def _stop_spinner(self) -> None:
        if self._live is not None:
            try:
                self._live.stop()
            finally:
                self._live = None
                self._working = None
        # The block being written was only on the transient display
        if self._pending:
            self._flush_reply()

    def _end_line(self) -> None:
        if self._mid_line:
            sys.stdout.write("\n")
            sys.stdout.flush()
            self._mid_line = False


def _always_scope(tool: str, label: str, arguments: Dict[str, Any]) -> str:
    """What "don't ask again" covers (see PermissionManager._remember), or "" if nothing."""
    from joshu.core.permissions import command_key

    if tool == "run_shell_command":
        key = command_key(str(arguments.get("command", "")))
        return f"`{key}` commands" if key else ""
    if tool in ("replace", "multi_edit", "notebook_edit"):
        return f"{label} edits" if tool == "notebook_edit" else "file edits"
    if tool == "write_file":
        return "creating files"
    return label


def _short(tokens: int) -> str:
    """1234 -> 1.2k, 12345 -> 12k."""
    if tokens < 1000:
        return str(tokens)
    if tokens < 10000:
        return f"{tokens / 1000:.1f}k"
    return f"{round(tokens / 1000)}k"


def render_diff(diff: str, limit: int) -> Any:
    """A unified diff with line numbers, additions green and removals red."""
    table = Table.grid(padding=(0, 1))
    table.add_column(justify="right", style="dim", no_wrap=True)
    table.add_column(no_wrap=False)
    old_no = new_no = 0
    shown = 0
    hidden = 0
    for line in diff.splitlines():
        if line.startswith(("---", "+++")):
            continue
        if line.startswith("@@"):
            try:
                ranges = line.split("@@")[1].split()
                old_no = int(ranges[0].split(",")[0].lstrip("-")) - 1
                new_no = int(ranges[1].split(",")[0].lstrip("+")) - 1
            except (IndexError, ValueError):
                pass
            if shown:
                table.add_row("", Text("⋮", style="dim"))
            continue
        if shown >= limit:
            hidden += 1
            continue
        if line.startswith("+"):
            new_no += 1
            table.add_row(str(new_no), Text("+ " + line[1:], style=_s("diff_add")))
        elif line.startswith("-"):
            old_no += 1
            table.add_row(str(old_no), Text("- " + line[1:], style=_s("diff_remove")))
        else:
            old_no += 1
            new_no += 1
            table.add_row(str(new_no), Text("  " + line[1:], style="dim"))
        shown += 1
    if hidden:
        table.add_row("", Text(f"… +{hidden} lines", style="dim"))
    return table


def _choose(question: str, options: List[tuple]) -> ApprovalChoice:
    """Arrow-key menu (prompt_toolkit), or a typed number without a terminal."""
    try:
        from prompt_toolkit.key_binding import KeyBindings
        from prompt_toolkit.shortcuts import choice

        bindings = KeyBindings()

        @bindings.add("escape", eager=True)
        def _(event):
            event.app.exit(result=ApprovalChoice.NO)

        for number, (value, _label) in enumerate(options, start=1):

            def pick(event, value=value):
                event.app.exit(result=value)

            bindings.add(str(number))(pick)

        if sys.stdin.isatty() and sys.stdout.isatty():
            labels = [(value, f"{n}. {label}") for n, (value, label) in enumerate(options, 1)]
            return choice(question, options=labels, symbol="❯", key_bindings=bindings)
    except (EOFError, KeyboardInterrupt):
        return ApprovalChoice.NO
    except ImportError:
        pass

    print(question)
    for number, (_value, label) in enumerate(options, start=1):
        print(f"  {number}. {label}")
    while True:
        try:
            answer = input("> ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print()
            return ApprovalChoice.NO
        if answer in ("", "1", "y", "yes"):
            return options[0][0]
        if answer.isdigit() and 1 <= int(answer) <= len(options):
            return options[int(answer) - 1][0]
        if answer in ("n", "no"):
            return ApprovalChoice.NO
        if answer in ("a", "always") and len(options) == 3:
            return options[1][0]


def _ask_feedback() -> Optional[str]:
    """Optional note for the model after declining (Enter to skip)."""
    try:
        note = input("  Tell Joshu what to do differently (Enter to skip): ").strip()
    except (EOFError, KeyboardInterrupt):
        print()
        return None
    return note or None


def _json(output: str) -> Optional[Dict[str, Any]]:
    text = output.lstrip()
    if not text.startswith("{"):
        return None
    try:
        data, _ = json.JSONDecoder().raw_decode(text)
    except ValueError:
        return None
    return data if isinstance(data, dict) else None


def _relative(path: str) -> str:
    """A path under the working directory, shown relative to it."""
    from pathlib import Path

    try:
        return str(Path(path).resolve().relative_to(Path.cwd().resolve()))
    except (ValueError, OSError):
        return path


def summarize_arguments(tool_name: str, arguments: Dict[str, Any], limit: int = 80) -> str:
    """One-line summary of a tool call's arguments."""
    if tool_name in _SUMMARY_KEYS and _SUMMARY_KEYS[tool_name] is None:
        return ""
    key = _SUMMARY_KEYS.get(tool_name)
    if key and key in arguments:
        value = str(arguments[key])
        if key == "path":
            value = _relative(value)
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
    from joshu.mcp.startup import load_mcp_tools

    config = get_config_manager()
    ui = ConsoleAgentUI(console, quiet=quiet)
    # MCP tools must be registered before the agent lists its tools
    load_mcp_tools(report=None if quiet else lambda line: ui.console.print(f"[dim]{line}[/dim]"))
    untrusted = getattr(config, "untrusted_project_config", None)
    if untrusted is not None and not quiet:
        ui.console.print(
            f"[yellow]Ignoring {untrusted}: run `joshu trust` to apply this project's settings."
            "[/yellow]"
        )
    for problem in configure_hooks_from_settings(config.get("hooks") or {}):
        ui.console.print(f"[yellow]Hook configuration: {problem}[/yellow]")
    from pathlib import Path

    from joshu.core.sandbox import configure_shell_sandbox

    shell_sandbox, sandbox_auto_allow, sandbox_warning = configure_shell_sandbox(
        config.get("shell_sandbox"), Path.cwd()
    )
    if sandbox_warning:
        ui.console.print(f"[yellow]{sandbox_warning}[/yellow]")
    elif shell_sandbox is not None and not quiet:
        ui.console.print(f"[dim]{shell_sandbox.describe()}[/dim]")

    if mode is None:
        mode = PermissionMode.from_string(config.get("permission_mode", "default"))
    permissions = PermissionManager(
        mode,
        approver=ui.approve if interactive else None,
        sandbox=sandbox,
        sandboxed_shell=sandbox_auto_allow,
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
