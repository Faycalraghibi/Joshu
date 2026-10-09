"""
More slash commands: /security-review, /pr-comments, /add-dir, /bashes, /hooks,
/output-style, /statusline, /sandbox, /terminal-setup and /release-notes.

Mixed into CommandHandler; output goes through rich (joshu.ui.display.console).
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from rich.table import Table
from rich.text import Text

from joshu.ui.theme import current_theme, style

SECURITY_REVIEW_PROMPT = """Do a security review of the current code changes in this repository.

Find them with `git status`, `git diff` and `git diff --staged`; if the working tree is clean, review the current branch against its base (`git diff main...HEAD`, or master). Read the surrounding code to understand how data flows in.

Look for: injection (SQL, shell, template, path traversal), missing authentication or authorization checks, secrets or credentials in code or logs, unsafe deserialization, SSRF and unvalidated URLs, insecure defaults (debug on, permissive CORS, weak crypto), unsafe file handling, and dependency changes that add risk.

For each finding give: severity (high / medium / low), file:line, how it could be exploited, and the fix. Only report issues you can point to in the code; say so if you find none. Don't modify any files."""

PR_COMMENTS_PROMPT = """Bring the review comments of {target} into this conversation.

Use the GitHub CLI: `gh pr view {ref}--json number,title,url,reviews,comments` for the review summaries and general comments, then `gh api repos/{{owner}}/{{repo}}/pulls/<number>/comments` for the inline code comments (get owner and repo with `gh repo view --json owner,name`).

Summarize them grouped by file, with line numbers, the reviewer and what they ask for. Mark which ones look resolved by the current code and which still need work, and suggest how to address each open one. Don't change any files yet."""

CHANGELOG_URL = "https://github.com/Faycalraghibi/Joshu/blob/main/CHANGELOG.md"


FEEDBACK_URL = "https://github.com/Faycalraghibi/Joshu/issues/new"
GITHUB_WORKFLOW = """name: Joshu
on:
  issue_comment:
    types: [created]
  pull_request_review_comment:
    types: [created]
permissions:
  contents: write
  pull-requests: write
  issues: write
jobs:
  joshu:
    if: >-
      contains(github.event.comment.body, '@joshu') &&
      contains(fromJSON('["OWNER", "MEMBER", "COLLABORATOR"]'), github.event.comment.author_association)
    runs-on: ubuntu-latest
    timeout-minutes: 30
    steps:
      - uses: actions/checkout@v4
      - uses: Faycalraghibi/Joshu@main
        env:
          {secret}: ${{{{ secrets.{secret} }}}}
        with:
          provider: {provider}
"""


def _confirm(question: str, default: bool) -> bool:
    """Yes / no with the arrow menu, or typed without a terminal."""
    from joshu.ui.menu import MenuUnavailable, menu

    options = [(True, "Yes"), (False, "No")]
    try:
        return bool(menu(question, options if default else options[::-1], cancel=False))
    except MenuUnavailable:
        try:
            answer = input(f"{question} [{'Y/n' if default else 'y/N'}] ").strip().lower()
        except EOFError:
            return False
        return default if not answer else answer in ("y", "yes")


def _console():
    from joshu.ui import display

    return display.console


class MoreCommands:
    """Mixin for CommandHandler (needs self.interactive_mode, self.config_manager)."""

    # --------------------------------------------------------------- reviews

    def cmd_security_review(self, arg: str = "") -> bool:
        return self._run_prompt(SECURITY_REVIEW_PROMPT, arg)

    def cmd_pr_comments(self, arg: str = "") -> bool:
        number = arg.strip().lstrip("#")
        if number and not number.isdigit():
            _console().print("Usage: /pr-comments [number]")
            return True
        target = f"pull request #{number}" if number else "the pull request for the current branch"
        prompt = PR_COMMENTS_PROMPT.format(target=target, ref=f"{number} " if number else "")
        return self._run_prompt(prompt, "")

    def _run_prompt(self, prompt: str, focus: str) -> bool:
        mode = self.interactive_mode
        if not mode._ensure_agent():
            return True
        if focus.strip():
            prompt += f"\n\nFocus on: {focus.strip()}"
        return mode._run_agent(prompt)

    # ---------------------------------------------------------------- paste

    def cmd_paste(self, arg: str = "") -> bool:
        from joshu.ui.clipboard import (
            ClipboardError,
            grab_clipboard_image,
            image_reference,
        )

        console = _console()
        try:
            path = grab_clipboard_image()
        except ClipboardError as e:
            console.print(str(e), highlight=False)
            return True
        if path is None:
            console.print("No image in the clipboard.")
            return True
        mode = self.interactive_mode
        pending = getattr(mode, "type_ahead", "") or ""
        mode.type_ahead = image_reference(path) + pending
        console.print(f"Attached {path.name}; add your request and press Enter.", highlight=False)
        return True

    # ----------------------------------------------------------------- dirs

    def cmd_add_dir(self, arg: str = "") -> bool:
        from joshu.tools.filesystem_tools import add_workspace_dir, workspace_dirs

        console = _console()
        if not arg.strip():
            console.print("Working directories:")
            for directory in workspace_dirs():
                console.print(f"  {directory}", highlight=False)
            console.print("Add one with /add-dir <path>.")
            return True
        try:
            directory = add_workspace_dir(arg.strip().strip('"'))
        except ValueError as e:
            console.print(str(e), highlight=False)
            return True
        mode = self.interactive_mode
        if mode._ensure_agent():
            mode.agent._pending_notes.append(
                f"[Note: the user added the directory {directory}; you can read and edit "
                "files there using absolute paths.]"
            )
        console.print(f"Added {directory} for this session.", highlight=False)
        return True

    # ------------------------------------------------------- conversation

    def cmd_copy(self, arg: str = "") -> bool:
        """/copy: the last reply to the clipboard."""
        from joshu.ui.clipboard import copy_text

        agent = self.interactive_mode.agent
        reply = agent.last_reply() if agent is not None else ""
        if not reply:
            _console().print("No reply to copy yet.")
            return True
        how = copy_text(reply)
        where = "through the terminal (OSC 52)" if how == "terminal" else "to the clipboard"
        _console().print(f"Copied the last reply ({len(reply):,} characters) {where}.")
        return True

    def cmd_rename(self, arg: str = "") -> bool:
        """/rename <title>"""
        title = " ".join(arg.split())
        agent = self.interactive_mode.agent
        if not title:
            _console().print("Usage: /rename <title>")
            return True
        if agent is None:
            _console().print("Nothing to rename yet: send a request first.")
            return True
        agent.title = title[:100]
        if agent.persist and len(agent.messages) > 1:
            agent._save()
        _console().print(f"Renamed this conversation to: {agent.title}")
        return True

    def cmd_fork(self, arg: str = "") -> bool:
        """/fork: continue in a copy; the original stays saved."""
        agent = self.interactive_mode.agent
        if agent is None or len(agent.messages) <= 1:
            _console().print("Nothing to fork yet: send a request first.")
            return True
        original = agent.fork()
        _console().print(
            f"Forked: you're now in {agent.session_id}. The original ({original}) is saved; "
            f"go back with /resume {original}."
        )
        return True

    # ------------------------------------------------------------- keys

    def cmd_login(self, arg: str = "") -> bool:
        """/login [provider]: save its API key in ~/.joshu/.env."""
        from joshu.core.credentials import save_key

        provider = self._provider(arg)
        if provider is None:
            return True
        if not provider.requires_key:
            _console().print(f"{provider.name} doesn't need an API key.")
            return True
        variable = provider.api_key_env or f"{provider.name.upper().replace('-', '_')}_API_KEY"
        from joshu.ui.menu import can_show_menu

        if not can_show_menu():
            _console().print(
                f"/login needs a terminal to type the key into. Or set {variable} in your "
                "environment or the project's .env."
            )
            return True
        try:
            from prompt_toolkit import prompt as ask

            key = ask(f"{provider.name} API key ({variable}): ", is_password=True).strip()
        except (EOFError, KeyboardInterrupt):
            key = ""
        if not key:
            _console().print("No key entered; nothing changed.")
            return True
        if not provider.api_key_env:
            self._set_key_variable(provider.name, variable)
        path = save_key(variable, key)
        self._refresh_client()
        _console().print(f"Saved {variable} in {path} (shown to no one). {provider.name} is ready.")
        return True

    def cmd_logout(self, arg: str = "") -> bool:
        """/logout [provider]"""
        import os

        from joshu.core.credentials import remove_key

        provider = self._provider(arg)
        if provider is None:
            return True
        variable = provider.api_key_env or f"{provider.name.upper().replace('-', '_')}_API_KEY"
        if remove_key(variable):
            _console().print(f"Removed {variable} from Joshu's saved keys.")
        else:
            _console().print(f"No saved key for {provider.name} ({variable}).")
        if os.environ.get(variable):
            _console().print(
                f"{variable} is still set in your environment or the project's .env; "
                "remove it there to log out completely."
            )
        return True

    def _provider(self, arg: str):
        from joshu.core.providers import DEFAULT_PROVIDER, get_providers

        config = self.interactive_mode.config_manager
        providers = get_providers(config.get("providers") or {})
        name = arg.strip() or str(config.get("provider") or DEFAULT_PROVIDER)
        if name not in providers:
            _console().print(f"Unknown provider '{name}'. Known: {', '.join(sorted(providers))}")
            return None
        return providers[name]

    def _set_key_variable(self, name: str, variable: str) -> None:
        config = self.interactive_mode.config_manager
        custom = dict(config.get("providers") or {})
        custom[name] = {**(custom.get(name) or {}), "api_key_env": variable}
        config.set("providers", custom)
        config.save_config()

    def _refresh_client(self) -> None:
        """Let the running conversation use the new key."""
        agent = self.interactive_mode.agent
        if agent is None:
            return
        from joshu.core.llm_client import LLMError, create_chat_client

        try:
            agent.client = create_chat_client(getattr(agent.client, "model", None))
        except LLMError:
            pass

    # --------------------------------------------------------- project setup

    def cmd_install_github_action(self, arg: str = "") -> bool:
        """/install-github-action: write .github/workflows/joshu.yml."""
        from joshu.core.providers import DEFAULT_PROVIDER, get_providers

        path = Path.cwd() / ".github" / "workflows" / "joshu.yml"
        if path.exists():
            _console().print(f"{path} already exists; edit it, or delete it to start over.")
            return True
        config = self.interactive_mode.config_manager
        provider_name = str(config.get("provider") or DEFAULT_PROVIDER)
        provider = get_providers(config.get("providers") or {}).get(provider_name)
        variable = (provider.api_key_env if provider else None) or "NVIDIA_API_KEY"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            GITHUB_WORKFLOW.format(provider=provider_name, secret=variable), encoding="utf-8"
        )
        _console().print(
            f"Wrote {path}.\nNext: add the repository secret {variable} (Settings > Secrets and "
            "variables > Actions), commit the file, then comment `@joshu <request>` on an issue "
            "or pull request."
        )
        return True

    def cmd_feedback(self, arg: str = "") -> bool:
        """/feedback [text]: open a pre-filled GitHub issue."""
        import platform
        import sys
        import urllib.parse
        import webbrowser

        from joshu import __version__

        body = (
            f"{arg.strip()}\n\n---\nJoshu {__version__}, Python {sys.version.split()[0]}, "
            f"{platform.system()} {platform.release()}, model "
            f"{self.interactive_mode.model_label() or '?'}"
        )
        url = (
            FEEDBACK_URL
            + "?"
            + urllib.parse.urlencode({"title": arg.strip()[:80] or "Feedback", "body": body})
        )
        opened = False
        try:
            opened = webbrowser.open(url)
        except Exception:
            opened = False
        _console().print(
            "Opened a new issue in your browser." if opened else f"Open this link: {url}"
        )
        return True

    # ------------------------------------------------------------------ btw

    def cmd_loop(self, arg: str = "") -> bool:
        """/loop [interval] <prompt> | stop: repeat a prompt (joshu.ui.interactive.loop)."""
        from .loop import (
            MAX_SECONDS,
            MIN_SECONDS,
            Loop,
            describe,
            parse_loop_args,
            short_duration,
        )

        mode = self.interactive_mode
        arg = arg.strip()
        if arg.lower() in ("stop", "off", "cancel", "end"):
            if mode.loop is None:
                _console().print("No loop is running.")
            else:
                _console().print(f"Stopped the loop after {mode.loop.runs} run(s).")
                mode.loop = None
            return True
        if not arg:
            if mode.loop is not None:
                _console().print(
                    f"Looping: {mode.loop.prompt}  ({describe(mode.loop)}, "
                    f"{mode.loop.runs} run(s); /loop stop ends it)"
                )
            else:
                _console().print(
                    "Usage: /loop [interval] <prompt>  e.g. /loop 5m check the CI and fix what "
                    "broke (default every 10m; /loop stop ends it)"
                )
            return True
        seconds, prompt = parse_loop_args(arg)
        if not prompt:
            _console().print("Usage: /loop [interval] <prompt>")
            return True
        if not MIN_SECONDS <= seconds <= MAX_SECONDS:
            _console().print(
                f"The interval must be between {short_duration(MIN_SECONDS)} and "
                f"{short_duration(MAX_SECONDS)}."
            )
            return True
        replaced = " (replaces the previous loop)" if mode.loop is not None else ""
        mode.loop = Loop(prompt, seconds)
        _console().print(
            f"Looping every {short_duration(seconds)}{replaced}: runs now, then "
            f"{short_duration(seconds)} after each run ends. /loop stop ends it."
        )
        return True

    def cmd_btw(self, arg: str = "") -> bool:
        """/btw <question>: answered from the conversation, not added to it."""
        question = arg.strip()
        if not question:
            _console().print("Usage: /btw <question>  (also while a task runs)")
            return True
        mode = self.interactive_mode
        if not mode._ensure_agent():
            return True
        try:
            answer = mode.agent.side_question(question)
        except Exception as e:
            _console().print(f"Couldn't answer: {e}")
            return True
        mode.agent_ui.show_side_answer(question, answer)
        return True

    # ----------------------------------------------------------------- jobs

    def cmd_background(self, arg: str = "") -> bool:
        """/background <request>: run it detached, in its own worktree."""
        from joshu.ui.cli_jobs import JobCommands

        mode = self.interactive_mode.config_manager.get("permission_mode", "default")
        JobCommands(_console()).start(
            arg,
            Path.cwd(),
            permission_mode=mode if mode in ("accept_edits", "bypass") else "accept_edits",
            model=getattr(self.interactive_mode, "model", None),
        )
        return True

    def cmd_jobs(self, arg: str = "") -> bool:
        """/jobs [show|apply|stop|log <id>]"""
        from joshu.ui.cli_jobs import JobCommands

        JobCommands(_console()).run(arg)
        return True

    # --------------------------------------------------------------- plugin

    def cmd_plugin(self, arg: str = "") -> bool:
        """/plugin: the `joshu plugin` commands inside a session."""
        from joshu.ui.cli_plugins import PluginCommands

        commands = PluginCommands(
            _console(),
            _confirm,
            applies="It works in this session now.",
        )
        commands.run(arg)
        words = arg.split()
        if words and words[0] in (
            "install",
            "add",
            "i",
            "remove",
            "uninstall",
            "rm",
            "update",
            "enable",
            "disable",
        ):
            self._plugins_changed()
        return True

    def _plugins_changed(self) -> None:
        """Let the running session use what was installed or removed."""
        from joshu.hooks import configure_hooks_from_settings

        configure_hooks_from_settings(self.interactive_mode.config_manager.get("hooks") or {})
        from joshu.mcp.startup import load_new_mcp_servers

        load_new_mcp_servers(report=lambda line: _console().print(f"[dim]{line}[/dim]"))
        agent = self.interactive_mode.agent
        if agent is not None:
            from joshu.core.subagents import discover_subagents

            agent.subagents = discover_subagents(agent.cwd)
            agent.reload_skills()
        refresh = getattr(self.interactive_mode, "_init_prompt_toolkit", None)
        if callable(refresh):
            refresh()

    # --------------------------------------------------------------- bashes

    def cmd_bashes(self, arg: str = "") -> bool:
        from joshu.tools.shell_tool import (
            list_background_processes,
            stop_background_process,
        )

        console = _console()
        theme = current_theme()
        parts = arg.split()
        if len(parts) == 2 and parts[0] == "kill":
            result = stop_background_process(parts[1])
            console.print(result.get("message") or result.get("error"), highlight=False)
            return True
        processes = list_background_processes()
        if not processes:
            console.print("No background commands. The agent starts them for long-running tasks.")
            return True
        if not arg.strip():
            from joshu.ui.menu import can_show_menu

            if can_show_menu():
                from joshu.ui.shell_viewer import run_viewer

                run_viewer()
                return True
        table = Table.grid(padding=(0, 2))
        for _ in range(4):
            table.add_column(no_wrap=True)
        for info in processes:
            code = info.process.poll()
            state = (
                Text("● running", style=style(theme.success))
                if code is None
                else Text(f"○ exited {code}", style="dim")
            )
            command = info.command if len(info.command) <= 60 else info.command[:57] + "..."
            table.add_row(info.process_id, state, info.started_at[11:19], Text(command))
        console.print(Text("Background commands", style="bold"))
        console.print(table)
        console.print(Text("/bashes kill <id> stops one, /bashes list prints this.", style="dim"))
        return True

    # ---------------------------------------------------------------- hooks

    def cmd_hooks(self, arg: str = "") -> bool:
        from joshu.hooks.dispatcher import configure_hooks_from_settings
        from joshu.hooks.events import HookEvent

        console = _console()
        hooks: Dict[str, List[Any]] = {
            str(k): list(v) if isinstance(v, list) else [v]
            for k, v in (self.config_manager.get("hooks") or {}).items()
        }
        events = [e.value for e in HookEvent]
        parts = arg.split(maxsplit=2)

        if parts and parts[0] in ("add", "remove"):
            if len(parts) < 3 or parts[1] not in events:
                console.print(
                    "Usage: /hooks add <event> <command>  or  /hooks remove <event> <n>\n"
                    f"Events: {', '.join(events)}",
                    highlight=False,
                )
                return True
            event = parts[1]
            if parts[0] == "add":
                hooks.setdefault(event, []).append(parts[2])
                message = f"Added a {event} hook."
            else:
                entries = hooks.get(event, [])
                if not parts[2].isdigit() or not 1 <= int(parts[2]) <= len(entries):
                    console.print(f"No {event} hook number {parts[2]}.", highlight=False)
                    return True
                entries.pop(int(parts[2]) - 1)
                if not entries:
                    hooks.pop(event, None)
                message = f"Removed {event} hook {parts[2]}."
            self.config_manager.set("hooks", hooks)
            self.config_manager.save_config()
            for problem in configure_hooks_from_settings(hooks):
                console.print(f"Hook configuration: {problem}", highlight=False)
            console.print(message, highlight=False)
            return True

        table = Table.grid(padding=(0, 2))
        table.add_column(no_wrap=True, style=style(current_theme().accent))
        table.add_column()
        for event in events:
            entries = hooks.get(event, [])
            if not entries:
                table.add_row(event, Text("-", style="dim"))
            for number, entry in enumerate(entries, 1):
                command = entry.get("command") if isinstance(entry, dict) else entry
                table.add_row(event if number == 1 else "", Text(f"{number}. {command}"))
        console.print(Text("Hooks", style="bold"))
        console.print(table)
        console.print(
            Text(
                "/hooks add <event> <command> · /hooks remove <event> <n> · see docs/hooks.md",
                style="dim",
            )
        )
        return True

    # --------------------------------------------------------- output style

    def cmd_output_style(self, arg: str = "") -> bool:
        from joshu.core.output_styles import available_styles

        console = _console()
        styles = available_styles()
        name = arg.strip().lower()
        if not name:
            current = self.config_manager.get("output_style") or "default"
            name = self._pick(
                "Choose an output style:",
                [(n, f"{n}: {s.description}") for n, s in styles.items()],
                current,
            )
            if not name:
                for n, s in styles.items():
                    marker = "●" if n == current else " "
                    console.print(f" {marker} {n:<12} {s.description}", highlight=False)
                console.print("Set one with /output-style <name>.")
                return True
        if name not in styles:
            console.print(f"Unknown style '{name}'. Styles: {', '.join(styles)}", highlight=False)
            return True
        self.config_manager.set("output_style", name)
        self.config_manager.save_config()
        agent = self.interactive_mode.agent
        if agent is not None:
            agent.refresh_system_prompt()
        console.print(f"Output style: {name}.", highlight=False)
        return True

    def _pick(self, question: str, options: List[tuple], default: Optional[str]) -> Optional[str]:
        try:
            from joshu.ui.menu import MenuUnavailable, menu

            return menu(question, options, default=default)
        except (EOFError, KeyboardInterrupt):
            return None
        except (ImportError, MenuUnavailable):
            pass
        return None

    # ----------------------------------------------------------- statusline

    def cmd_statusline(self, arg: str = "") -> bool:
        console = _console()
        command = arg.strip()
        if not command:
            current = self.config_manager.get("statusline") or ""
            console.print(
                f"Status line command: {current}" if current else "No status line command set.",
                highlight=False,
            )
            console.print(
                "Set one with /statusline <command>; it gets the session as JSON on stdin "
                "and its first output line is shown under the input. /statusline off removes it.",
                highlight=False,
            )
            return True
        if command in ("off", "none", "clear"):
            command = ""
        self.config_manager.set("statusline", command)
        self.config_manager.save_config()
        statusline = getattr(self.interactive_mode, "statusline", None)
        if statusline is not None:
            statusline.reset()
        console.print("Status line removed." if not command else "Status line set.")
        return True

    # -------------------------------------------------------------- sandbox

    def cmd_sandbox(self, arg: str = "") -> bool:
        from joshu.core.sandbox import MODES, backend_available, configure_shell_sandbox

        console = _console()
        current = dict(self.config_manager.get("shell_sandbox") or {})
        mode = arg.strip().lower()
        if not mode:
            console.print(f"Shell sandbox: {current.get('mode', 'off')}", highlight=False)
            for backend in ("bubblewrap", "seatbelt", "docker"):
                available = backend_available(backend)
                console.print(
                    f"  {'✓' if available else '✗'} {backend}"
                    + ("" if available else "  (not available here)"),
                    highlight=False,
                )
            console.print(f"Set it with /sandbox <{'|'.join(MODES)}>.", highlight=False)
            return True
        if mode not in MODES:
            console.print(f"Unknown mode '{mode}'. Modes: {', '.join(MODES)}", highlight=False)
            return True
        current["mode"] = mode
        self.config_manager.set("shell_sandbox", current)
        self.config_manager.save_config()
        sandbox, auto_allow, warning = configure_shell_sandbox(current, Path.cwd())
        agent = self.interactive_mode.agent
        if agent is not None:
            agent.permissions.sandboxed_shell = auto_allow
        if warning:
            console.print(warning, highlight=False)
        elif sandbox is not None:
            console.print(f"Sandbox on: {sandbox.describe()}", highlight=False)
        else:
            console.print("Sandbox off: shell commands run directly and ask for approval.")
        return True

    # -------------------------------------------------------- terminal setup

    def cmd_terminal_setup(self, arg: str = "") -> bool:
        console = _console()
        terminal = detect_terminal()
        from rich.markdown import Markdown

        console.print(Markdown(terminal_instructions(terminal)))
        return True

    # --------------------------------------------------------- release notes

    def cmd_release_notes(self, arg: str = "") -> bool:
        from joshu import __version__

        console = _console()
        notes = release_notes(__version__)
        if notes is None:
            console.print(f"Release notes: {CHANGELOG_URL}", highlight=False)
            return True
        from rich.markdown import Markdown

        console.print(Markdown(notes))
        return True


# ------------------------------------------------------------------ helpers


def detect_terminal() -> str:
    if os.environ.get("TERM_PROGRAM") == "vscode":
        return "vscode"
    if os.environ.get("WT_SESSION"):
        return "windows-terminal"
    if os.environ.get("TERM_PROGRAM") == "iTerm.app":
        return "iterm2"
    return "other"


def terminal_instructions(terminal: str) -> str:
    common = (
        "Joshu inserts a new line with **Alt+Enter**, or **`\\` then Enter**. "
        "To use **Shift+Enter** instead, make your terminal send Alt+Enter for it:\n\n"
    )
    if terminal == "windows-terminal":
        return common + (
            "**Windows Terminal**: open Settings → *Open JSON file* and add to `actions` "
            "(newer versions: also add the key under `keybindings`):\n\n"
            "```json\n"
            '{ "command": { "action": "sendInput", "input": "\\u001b\\r" }, "keys": "shift+enter" }\n'
            "```"
        )
    if terminal == "vscode":
        return common + (
            "**VS Code terminal**: run *Preferences: Open Keyboard Shortcuts (JSON)* and add:\n\n"
            "```json\n"
            '{ "key": "shift+enter", "command": "workbench.action.terminal.sendSequence",\n'
            '  "args": { "text": "\\u001b\\r" }, "when": "terminalFocus" }\n'
            "```"
        )
    if terminal == "iterm2":
        return common + (
            "**iTerm2**: Settings → Profiles → Keys → Key Mappings → **+**, press Shift+Enter, "
            "choose *Send Escape Sequence* and type a carriage return (or pick the "
            "*Natural Text Editing* preset)."
        )
    return common + (
        "Map Shift+Enter to send `ESC` followed by `Enter` (`\\x1b\\r`) in your terminal's "
        "key settings. Supported setups: Windows Terminal, VS Code and iTerm2."
    )


def release_notes(version: str, sections: int = 2) -> Optional[str]:
    """The newest CHANGELOG sections (Unreleased and the current version), if found."""
    import joshu

    candidates = [Path(joshu.__file__).resolve().parents[2] / "CHANGELOG.md"]
    for path in candidates:
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        headings = [m.start() for m in re.finditer(r"^## \[", text, flags=re.MULTILINE)]
        if not headings:
            return None
        end = headings[sections] if len(headings) > sections else len(text)
        body = text[headings[0] : end].strip()
        lines = body.splitlines()
        if len(lines) > 80:
            body = "\n".join(lines[:80]) + f"\n\n… more in {CHANGELOG_URL}"
        return f"# Joshu {version}\n\n" + body
    return None
