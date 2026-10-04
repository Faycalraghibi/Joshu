"""
Slash commands that inspect or configure the session: /status, /doctor,
/context, /todos, /export, /review, /mcp, /theme, /vim and /help.

Mixed into CommandHandler; output goes through rich (joshu.ui.display.console).
"""

from __future__ import annotations

import json
import platform
import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from rich.console import Group
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from joshu.ui.interactive.command_registry import COMMANDS, GROUPS
from joshu.ui.theme import GLYPH, THEMES, current_theme, style

REVIEW_PROMPT = """Review the current code changes in this repository.

Find them with `git status` and `git diff` (also `git diff --staged`). If the working tree is clean, review the current branch against its base (`git diff main...HEAD`, or master). Read the surrounding code where you need context.

Report, most important first:
1. Bugs: incorrect behavior, crashes, security problems, with file:line and why
2. Risky spots: missing error handling, edge cases, missing tests
3. Brief suggestions (only if worthwhile)

Don't modify any files. If there is nothing to review, say so."""

SHORTCUTS_ROWS = [
    ("!", "run a shell command"),
    ("/", "commands"),
    ("@", "attach a file or image"),
    ("esc", "interrupt the agent / clear input"),
    ("shift+tab", "cycle modes: default, accept edits, plan"),
    ("tab", "complete"),
    ("ctrl+r", "search history"),
    ("ctrl+c", "clear input (twice to exit)"),
    ("ctrl+d", "exit"),
]


def _console():
    from joshu.ui import display

    return display.console


def _check(ok: Optional[bool], text: str, detail: str = "") -> Text:
    theme = current_theme()
    if ok is True:
        mark, color = "✓", theme.success
    elif ok is False:
        mark, color = "✗", theme.error
    else:
        mark, color = "!", theme.warning
    line = Text.assemble((f"  {mark} ", style(color, "bold")), text)
    if detail:
        line.append(f"  {detail}", style="dim")
    return line


class ExtraCommands:
    """Mixin for CommandHandler (needs self.interactive_mode, self.config_manager)."""

    # ------------------------------------------------------------------ help

    def show_help(self) -> None:
        theme = current_theme()
        console = _console()
        console.print(Text.assemble((f"{GLYPH} ", style(theme.accent)), ("Joshu commands", "bold")))
        for group in GROUPS:
            table = Table.grid(padding=(0, 2))
            table.add_column(style=style(theme.accent), no_wrap=True, min_width=22)
            table.add_column()
            for command in (c for c in COMMANDS if c.group == group):
                aliases = (
                    "  " + ", ".join("/" + a for a in command.aliases) if command.aliases else ""
                )
                table.add_row(Text(command.usage), Text(command.description + aliases))
            console.print(Text(f"\n{group}", style="bold"))
            console.print(table)

        custom = self._custom_entries()
        if custom:
            table = Table.grid(padding=(0, 2))
            table.add_column(style=style(theme.secondary), no_wrap=True, min_width=22)
            table.add_column()
            for name, description in custom:
                table.add_row(Text(name), Text(description))
            console.print(Text("\nCustom commands and skills", style="bold"))
            console.print(table)

        shortcuts = Table.grid(padding=(0, 2))
        shortcuts.add_column(style=style(theme.accent), no_wrap=True, min_width=22)
        shortcuts.add_column()
        for key, description in SHORTCUTS_ROWS:
            shortcuts.add_row(Text(key), Text(description))
        console.print(Text("\nShortcuts", style="bold"))
        console.print(shortcuts)

    def _custom_entries(self) -> List[tuple]:
        entries = []
        try:
            from joshu.core.custom_commands import discover_commands
            from joshu.core.skills import discover_skills

            for name, command in sorted(discover_commands().items()):
                entries.append((f"/{name}", command.description or "custom command"))
            for name, skill in sorted(discover_skills().items()):
                entries.append((f"/{name}", f"skill: {skill.description}"))
        except Exception:
            pass
        return entries

    # ---------------------------------------------------------------- status

    def cmd_status(self, arg: str = "") -> bool:
        from joshu import __version__
        from joshu.core.auto_memory import list_memories
        from joshu.core.instructions import instruction_files
        from joshu.core.providers import DEFAULT_PROVIDER

        mode = self.interactive_mode
        agent = mode.agent
        config = self.config_manager
        theme = current_theme()

        rows = [
            ("Version", f"{__version__} (Python {platform.python_version()})"),
            ("Directory", str(Path.cwd())),
            ("Session", getattr(agent, "session_id", None) or "not started"),
            ("Provider", str(config.get("provider") or DEFAULT_PROVIDER)),
            ("Model", mode.model_label() or "-"),
            ("Mode", mode.current_mode().replace("_", " ")),
            ("Theme", theme.name),
        ]
        files = [str(p) for p in instruction_files(Path.cwd())]
        rows.append(("Instructions", "\n".join(files) if files else "none (run /init)"))
        rows.append(
            (
                "Memory",
                f"{len(list_memories('project'))} project, {len(list_memories('user'))} user",
            )
        )
        rows.append(("Skills", str(len(getattr(agent, "skills", {}) or self._skills()))))
        rows.append(("MCP servers", str(len(self._mcp_status()))))
        layers = getattr(config, "layers", []) or []
        rows.append(("Config", "\n".join(f"{name}: {path}" for name, path in layers) or "-"))

        table = Table.grid(padding=(0, 2))
        table.add_column(style="dim", no_wrap=True)
        table.add_column()
        for key, value in rows:
            table.add_row(Text(key), Text(str(value)))
        _console().print(
            Panel(table, title=f"{GLYPH} Joshu status", border_style=style(theme.accent))
        )
        return True

    def _skills(self) -> Dict[str, Any]:
        try:
            from joshu.core.skills import discover_skills

            return discover_skills()
        except Exception:
            return {}

    # ---------------------------------------------------------------- doctor

    def cmd_doctor(self, arg: str = "") -> bool:
        from joshu.core.model_catalog import check_model, resolve_named_model
        from joshu.core.providers import DEFAULT_PROVIDER, ProviderError, get_providers

        console = _console()
        config = self.config_manager
        console.print(Text(f"{GLYPH} Checking your setup", style="bold"))

        ok_python = sys.version_info >= (3, 10)
        console.print(_check(ok_python, f"Python {platform.python_version()}"))

        try:
            providers = get_providers(config.get("providers") or {})
        except ProviderError as e:
            console.print(_check(False, "Provider configuration", str(e)))
            return True
        name = config.get("provider") or DEFAULT_PROVIDER
        model = config.get("model")
        named = resolve_named_model(model)
        if named is not None:
            name, model = named.provider, named.model
        provider = providers.get(name)
        if provider is None:
            console.print(_check(False, f"Provider '{name}'", "unknown: see joshu providers"))
            return True
        console.print(_check(True, f"Provider {name}", provider.base_url))

        if provider.requires_key:
            source = provider.api_key_env or "api_key in config"
            console.print(
                _check(
                    provider.is_configured(),
                    "API key",
                    f"{source} {'set' if provider.is_configured() else 'missing'}",
                )
            )
            if not provider.is_configured():
                return True

        model = model or provider.default_model
        if not model:
            console.print(_check(False, "Model", "none set: joshu use <model>"))
            return True
        with console.status(f"Checking {model}…"):
            result = check_model(provider, model)
        if not result.ok:
            console.print(_check(False, f"Model {model}", result.error[:200]))
        elif result.tool_call:
            console.print(
                _check(True, f"Model {model}", f"answers and calls tools ({result.seconds:.1f}s)")
            )
        else:
            console.print(_check(None, f"Model {model}", "answers but didn't call the test tool"))

        for tool, purpose in (
            ("git", "version control"),
            ("rg", "fast search"),
            ("node", "JavaScript checks"),
        ):
            found = shutil.which(tool)
            console.print(_check(True if found else None, tool, found or f"not found ({purpose})"))

        untrusted = getattr(config, "untrusted_project_config", None)
        if untrusted is not None:
            console.print(_check(None, "Project config", f"{untrusted} ignored: run joshu trust"))
        return True

    # --------------------------------------------------------------- context

    def cmd_context(self, arg: str = "") -> bool:
        from joshu.core.compaction import estimate_tokens

        agent = self.interactive_mode.agent
        console = _console()
        theme = current_theme()
        if agent is None:
            console.print("No conversation yet.")
            return True

        window = int(agent.context_window or 128000)
        system = estimate_tokens(agent.messages[:1])
        tools = len(json.dumps([s.to_openai_format() for s in agent.tool_specs()])) // 4
        conversation = estimate_tokens(agent.messages[1:])
        used = system + tools + conversation
        threshold = int(window * agent.compact_threshold)

        cells = 40
        parts = [(system, theme.secondary), (tools, theme.plan), (conversation, theme.accent)]
        bar = Text()
        filled = 0
        for tokens, color in parts:
            count = min(cells - filled, round(cells * tokens / window))
            bar.append("█" * count, style=style(color))
            filled += count
        bar.append("░" * (cells - filled), style="dim")

        console.print(
            Text.assemble(
                ("Context  ", "bold"), bar, f"  {used:,} / {window:,} tokens ({used / window:.0%})"
            )
        )
        table = Table.grid(padding=(0, 2))
        table.add_column(no_wrap=True)
        table.add_column(justify="right")
        table.add_row(Text("█ System prompt", style=style(theme.secondary)), f"{system:,}")
        table.add_row(Text("█ Tools", style=style(theme.plan)), f"{tools:,}")
        table.add_row(Text("█ Conversation", style=style(theme.accent)), f"{conversation:,}")
        table.add_row(Text("░ Free", style="dim"), f"{max(0, window - used):,}")
        console.print(table)
        console.print(
            Text(
                f"Compacts automatically at {threshold:,} tokens; /compact to do it now.",
                style="dim",
            )
        )
        return True

    # ----------------------------------------------------------------- todos

    def cmd_todos(self, arg: str = "") -> bool:
        agent = self.interactive_mode.agent
        todos = _latest_todos(agent.messages) if agent is not None else None
        console = _console()
        if not todos:
            console.print("No todos in this conversation.")
            return True
        for todo in todos:
            status = todo.get("status", "pending")
            text = str(todo.get("description", ""))
            if status in ("completed", "cancelled"):
                console.print(Text(f"  ☒ {text}", style="dim strike"))
            elif status == "in_progress":
                console.print(Text(f"  ☐ {text}", style="bold"))
            else:
                console.print(f"  ☐ {text}", highlight=False)
        return True

    # ---------------------------------------------------------------- export

    def cmd_export(self, arg: str = "") -> bool:
        agent = self.interactive_mode.agent
        console = _console()
        if agent is None or len(agent.messages) <= 1:
            console.print("Nothing to export yet.")
            return True
        name = arg.strip() or f"joshu-conversation-{datetime.now():%Y%m%d-%H%M%S}.md"
        path = Path(name).expanduser()
        if not path.suffix:
            path = path.with_suffix(".md")
        try:
            path.write_text(conversation_markdown(agent.messages), encoding="utf-8")
        except OSError as e:
            console.print(f"Could not write {path}: {e}")
            return True
        console.print(f"Saved the conversation to {path}", highlight=False)
        return True

    # ---------------------------------------------------------------- review

    def cmd_review(self, arg: str = "") -> bool:
        mode = self.interactive_mode
        if not mode._ensure_agent():
            return True
        prompt = REVIEW_PROMPT + (f"\n\nFocus on: {arg.strip()}" if arg.strip() else "")
        return mode._run_agent(prompt)

    # ------------------------------------------------------------------- mcp

    def _mcp_status(self) -> Dict[str, Dict[str, Any]]:
        try:
            from joshu.mcp.registry import get_mcp_registry

            return get_mcp_registry().get_status()
        except Exception:
            return {}

    def cmd_mcp(self, arg: str = "") -> bool:
        console = _console()
        theme = current_theme()
        status = self._mcp_status()
        if not status:
            console.print(
                "No MCP servers. Add them with `joshu mcp add` or in config/mcp.json "
                "(see docs/mcp-servers.md)."
            )
            return True
        counts: Dict[str, int] = {}
        try:
            from joshu.core.tool_registry import ToolRegistry

            for spec in ToolRegistry().get_available_tools(enabled_only=True):
                server = getattr(getattr(spec.function, "definition", None), "server_name", None)
                if server:
                    counts[server] = counts.get(server, 0) + 1
        except Exception:
            pass
        table = Table.grid(padding=(0, 2))
        table.add_column(no_wrap=True)
        table.add_column(no_wrap=True)
        table.add_column(justify="right")
        table.add_column(style="dim")
        for name, info in sorted(status.items()):
            if not info.get("enabled", True):
                state = Text("○ disabled", style="dim")
            elif info.get("connected"):
                state = Text("● connected", style=style(theme.success))
            else:
                state = Text("○ not connected", style=style(theme.warning))
            target = info.get("url") or info.get("command") or ""
            table.add_row(name, state, f"{counts.get(name, 0)} tools", str(target))
        console.print(Text("MCP servers", style="bold"))
        console.print(table)
        return True

    # ----------------------------------------------------------------- theme

    def cmd_theme(self, arg: str = "") -> bool:
        console = _console()
        name = arg.strip().lower()
        if not name:
            name = self._pick_theme()
            if not name:
                return True
        if name not in THEMES:
            console.print(f"Unknown theme '{name}'. Themes: {', '.join(THEMES)}")
            return True
        self.config_manager.set("theme", name)
        self.config_manager.save_config()
        mode = self.interactive_mode
        if hasattr(mode, "_init_prompt_toolkit"):
            from joshu.ui.interactive.prompt import get_style

            mode.style = get_style()
        _preview_theme(name)
        console.print(f"Theme set to {THEMES[name].label}.", highlight=False)
        return True

    def _pick_theme(self) -> Optional[str]:
        current = current_theme().name
        options = [(name, theme.label) for name, theme in THEMES.items()]
        try:
            from prompt_toolkit.shortcuts import choice

            if sys.stdin.isatty():
                return choice("Choose a theme:", options=options, default=current, symbol="❯")
        except (EOFError, KeyboardInterrupt):
            return None
        except ImportError:
            pass
        _console().print("Themes: " + ", ".join(THEMES) + "  (/theme <name>)")
        return None

    # ------------------------------------------------------------------- vim

    def cmd_vim(self, arg: str = "") -> bool:
        mode = self.interactive_mode
        mode.vim_enabled = not getattr(mode, "vim_enabled", False)
        if not mode.vim_enabled:
            mode.vim_mode = "INSERT"
        self.config_manager.set("vim_mode", mode.vim_enabled)
        self.config_manager.save_config()
        state = "on: Esc for NORMAL mode, i to insert" if mode.vim_enabled else "off"
        _console().print(f"Vim keys {state}.", highlight=False)
        return True


def _latest_todos(messages: List[Dict[str, Any]]) -> Optional[List[Dict[str, Any]]]:
    for message in reversed(messages):
        for call in reversed(message.get("tool_calls") or []):
            function = call.get("function") or {}
            if function.get("name") == "write_todos":
                try:
                    todos = json.loads(function.get("arguments") or "{}").get("todos")
                except (ValueError, AttributeError):
                    continue
                if isinstance(todos, list):
                    return [t for t in todos if isinstance(t, dict)]
    return None


def conversation_markdown(messages: List[Dict[str, Any]]) -> str:
    """A readable Markdown transcript: requests, replies and the tools used."""
    from joshu.core.images import message_text

    lines = [f"# Joshu conversation ({datetime.now():%Y-%m-%d %H:%M})", ""]
    for message in messages[1:]:
        role = message.get("role")
        text = message_text(message.get("content")).strip()
        if role == "user" and text:
            lines += ["## You", "", text, ""]
        elif role == "assistant":
            if text:
                lines += ["## Joshu", "", text, ""]
            for call in message.get("tool_calls") or []:
                function = call.get("function") or {}
                arguments = function.get("arguments") or ""
                try:
                    parsed = json.loads(arguments)
                    shown = next(iter(parsed.values())) if len(parsed) == 1 else arguments
                except (ValueError, AttributeError, StopIteration):
                    shown = arguments
                shown = " ".join(str(shown).split())
                if len(shown) > 120:
                    shown = shown[:117] + "..."
                lines.append(f"- `{function.get('name')}` {shown}")
            if message.get("tool_calls"):
                lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _preview_theme(name: str) -> None:
    from joshu.ui.agent_ui import render_diff

    theme = THEMES[name]
    console = _console()
    sample = "--- a/x.py\n+++ b/x.py\n@@ -1,2 +1,2 @@\n def total(items):\n-    return sum(items) + 1\n+    return sum(items)\n"
    console.print(
        Panel(
            Group(
                Text.assemble(("● ", style(theme.accent)), ("Update", "bold"), "(x.py)"),
                render_diff(sample, 10),
            ),
            title=theme.label,
            border_style=style(theme.accent),
            expand=False,
        )
    )
