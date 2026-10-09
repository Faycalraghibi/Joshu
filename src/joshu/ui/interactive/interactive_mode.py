"""Main interactive mode implementation."""

import time
from pathlib import Path
from typing import Optional

try:
    from prompt_toolkit.shortcuts import prompt

    PROMPT_TOOLKIT_AVAILABLE = True
except ImportError:
    prompt = None
    PROMPT_TOOLKIT_AVAILABLE = False

from joshu.core.config import get_config_manager
from joshu.core.context_provider import ContextProvider
from joshu.tools.shell import run_command

from .commands import CommandHandler
from .completers import get_command_completer, get_path_completer
from .history import JsonHistory
from .keybindings import create_key_bindings, vi_normal_mode
from .modes import AskModeHandler
from .prompt import (
    MODE_HINTS,
    PLACEHOLDER,
    SHORTCUTS,
    bottom_toolbar,
    get_style,
    prompt_message,
)

# The context use shows in the bar once it passes this many percent
CONTEXT_SHOWN_FROM = 50


# Loaded on a thread while the prompt waits for you: the first request
# needs them, and the OpenAI SDK alone takes about two seconds to import
WARM_UP_MODULES = (
    "openai",
    "joshu.core.agent",
    "joshu.ui.agent_ui",
    "rich.markdown",
    "joshu.core.repo_map",
)


def warm_up_in_background() -> None:
    """Import what the first request needs while the user types it."""
    import importlib
    import threading

    def warm_up() -> None:
        for name in WARM_UP_MODULES:
            try:
                importlib.import_module(name)
            except Exception:  # only a head start: the request imports it anyway
                pass

    threading.Thread(target=warm_up, name="joshu-warm-up", daemon=True).start()


def side_question_text(line: str) -> Optional[str]:
    """The question in `/btw <question>`, or None for other input."""
    text = line.strip()
    if not text.lower().startswith("/btw"):
        return None
    question = text[4:].strip()
    return question or None


class InteractiveMode:
    """Main interactive mode with advanced terminal features."""

    def __init__(self, model: str, sandbox: bool = False, verbose: bool = False):
        self.model = model
        self.sandbox = sandbox
        self.config_manager = get_config_manager()

        self.max_history_entries = self.config_manager.get("history_limit", 1000)

        self.context_provider = ContextProvider()

        self.prompt_history = JsonHistory()

        # Vim keys only when enabled in config (vim_mode: true)
        self.vim_enabled = bool(self.config_manager.get("vim_mode", False))
        # One-line notice shown in place of the mode hint (e.g. "press Ctrl+C again")
        self.notice = ""
        from .statusline import StatusLine

        # Messages sent (Enter) while a request ran: they go next, one by one
        self.queued: list = []
        self._background_started = False
        # How full the context window is, for the bar under the input
        self.context_level: Optional[int] = None

        self.statusline = StatusLine()
        self._bypass_cycle = self.config_manager.get(
            "permission_mode", "default"
        ) == "bypass" and self.config_manager.get("allow_bypass", True)
        self.multiline_mode = False
        self.verbose_mode = verbose
        self.suggestions_enabled = True
        self.interaction_mode = "agent"

        if verbose:
            import logging

            logging.getLogger().setLevel(logging.DEBUG)
            logging.getLogger("joshu").setLevel(logging.DEBUG)
            logging.getLogger("joshu.core").setLevel(logging.DEBUG)

        self.command_history = []
        self.bash_history = []
        self._history_index = -1

        self.ask_handler = AskModeHandler(self)
        # Tool-using agent for agent and plan modes, created on first use
        self.agent = None
        self.agent_ui = None
        self.command_handler = CommandHandler(self)
        # Text typed while the agent was working, offered as the next prompt
        self.type_ahead = ""

        if PROMPT_TOOLKIT_AVAILABLE:
            self._init_prompt_toolkit()

        self._load_history()

    def _init_prompt_toolkit(self):
        """Initialize prompt_toolkit components."""
        if not PROMPT_TOOLKIT_AVAILABLE:
            return

        self.key_bindings = create_key_bindings(self)
        self.style = get_style()
        self.path_completer = get_path_completer()
        try:
            from joshu.core.custom_commands import discover_commands
            from joshu.core.skills import discover_skills
            from joshu.mcp.extras import list_prompts

            custom = (
                [
                    (f"/{name}", command.description or "custom command")
                    for name, command in discover_commands().items()
                ]
                + [
                    (f"/{p.command}", f"MCP prompt: {p.description}".strip(": "))
                    for p in list_prompts()
                ]
                + [
                    (f"/{name}", f"skill: {skill.description}")
                    for name, skill in discover_skills().items()
                ]
            )
        except Exception:  # a broken command file shouldn't stop the REPL
            custom = []
        self.command_completer = get_command_completer(custom)

    def _load_history(self):
        """Load command history from JSON storage."""
        self.command_history = self.prompt_history.load_history_strings()[
            : self.max_history_entries
        ]

    def _add_to_history(self, command: str):
        """Add command to history."""
        if command and command.strip():
            self.prompt_history.store_string(command)
            if not self.command_history or self.command_history[-1] != command:
                self.command_history.append(command)
                if len(self.command_history) > self.max_history_entries:
                    self.command_history = self.command_history[-self.max_history_entries :]

    def _handle_bash_command(self, command: str):
        """Handle bash command with ! prefix."""
        if not command.startswith("!"):
            return

        bash_cmd = command[1:]

        if bash_cmd == "!":
            if self.bash_history:
                bash_cmd = self.bash_history[-1]
            else:
                self._show_message("No bash command history")
                return
        elif bash_cmd.startswith("!"):
            try:
                n = int(bash_cmd[1:])
                if 0 < n <= len(self.bash_history):
                    bash_cmd = self.bash_history[n - 1]
                else:
                    self._show_message(f"Invalid bash command number: {n}")
                    return
            except ValueError:
                pattern = bash_cmd[1:]
                matches = [cmd for cmd in self.bash_history if pattern in cmd]
                if matches:
                    bash_cmd = matches[-1]
                else:
                    self._show_message(f"No bash command matching: {pattern}")
                    return

        from joshu.core.skill_install import skills_add_part

        if skills_add_part(bash_cmd) is not None:
            # Install where Joshu finds skills (see /skills add)
            self.bash_history.append(bash_cmd)
            self.command_handler.handle_skill_add(skills_add_part(bash_cmd) or bash_cmd)
            return

        try:
            code, out, err = run_command(bash_cmd)
            self.bash_history.append(bash_cmd)
            if out:
                self._show_message(out)
            if err:
                self._show_message(f"Error: {err}")
        except Exception as e:
            self._show_message(f"Error executing command: {str(e)}")

    def _handle_user_input(self, user_input: str) -> bool:
        """Handle user input and return True if session should continue."""
        self.notice = ""
        if not user_input or not user_input.strip():
            return True
        if user_input.strip() == "?":
            self.show_shortcuts()
            return True

        self._add_to_history(user_input)

        if self.context_provider:
            self.context_provider.add_to_history(
                "user",
                user_input,
                metadata={"mode": self.interaction_mode, "timestamp": time.time()},
            )

        if user_input.startswith("/"):
            return self.command_handler.handle_slash_command(user_input)
        elif user_input.startswith("!"):
            self._handle_bash_command(user_input)
            return True

        if self.interaction_mode == "ask":
            return self.ask_handler.handle(user_input)

        if self._ensure_agent():
            return self._run_agent(user_input)
        return True

    def _ensure_agent(self) -> bool:
        """Create the agent on first use; False when no model endpoint is configured."""
        if self.agent is not None:
            return True

        from joshu.core.llm_client import LLMError
        from joshu.ui.agent_ui import create_console_agent

        try:
            self.agent, self.agent_ui = create_console_agent(model=self.model, sandbox=self.sandbox)
            return True
        except LLMError as e:
            self._show_message(f"Model unavailable: {e}")
            self._show_message("Run `joshu providers` to pick a provider and set its API key.")
            return False

    def run_custom_command(self, command: str) -> bool:
        """Expand a custom slash command and run its prompt through the agent."""
        from joshu.core.custom_commands import expand_slash_command

        if not self._ensure_agent():
            return True
        prompt = expand_slash_command(command, self.agent.permissions)
        if prompt is None:
            self._show_message(f"Unknown command: {command.split()[0]}")
            return True
        return self._run_agent(prompt)

    def resume_session(self, session_id: Optional[str] = None) -> bool:
        """
        Continue a saved agent session: the given id, or the latest one here.

        Returns False (after explaining why) when nothing was resumed.
        """
        from joshu.core.sessions import SessionError, latest_session, load_session

        if not self._ensure_agent():
            return False

        if session_id is None:
            latest = latest_session(self.agent.cwd)
            if latest is None:
                self._show_message("No previous session in this directory.")
                return False
            session_id = latest.id

        try:
            session = load_session(session_id)
        except SessionError as e:
            self._show_message(str(e))
            return False

        self.agent.restore(session)
        self._show_message(
            f"Resumed session {session['id']} ({len(session['messages'])} messages): "
            f"{session.get('title', '')}"
        )
        return True

    def _run_agent(self, user_input: str) -> bool:
        """Run one request through the tool-using agent."""
        from joshu.core.llm_client import LLMError
        from joshu.core.permissions import PermissionMode

        if self.interaction_mode == "plan":
            mode = PermissionMode.PLAN
        else:
            mode = PermissionMode.from_string(self.config_manager.get("permission_mode", "default"))
        if self.agent.permissions.mode != mode:
            self.agent.set_mode(mode)

        from joshu.core.file_refs import attach_file_refs
        from joshu.core.images import ImageError, find_image_refs
        from joshu.mcp.extras import with_resources

        prompt, images = find_image_refs(user_input)
        prompt = with_resources(prompt)
        prompt, files = attach_file_refs(prompt)
        names = [path.name for path in images] + files
        if names:
            self._show_message("Attached: " + ", ".join(names))

        from joshu.mcp.startup import background_report
        from joshu.tools.shell_tool import set_detachable
        from joshu.ui.key_listener import CTRL_B, CTRL_O, KeyListener

        while background_report:  # what the MCP servers reported while starting
            self._show_message(background_report.pop(0))
        self.agent_ui.begin_request()
        set_detachable(True)
        listener = KeyListener(
            {CTRL_O: self.agent_ui.toggle_verbose, CTRL_B: self._move_to_background},
            on_submit=self._submit_while_running,
        )
        from joshu.ui import agent_ui as agent_ui_module

        agent_ui_module.queued_messages = lambda: list(self.queued)
        agent_ui_module.input_hint = self._mode_hint
        try:
            with listener:
                response = self.agent.run(prompt, images=images)
        except KeyboardInterrupt:
            self._show_message("\nInterrupted. Send a follow-up, or /rewind to drop that request.")
            return True
        except ImageError as e:
            self._show_message(str(e))
            return True
        except LLMError as e:
            self._show_message(f"Model error: {e}")
            return True
        finally:
            self.type_ahead = listener.typed
            self.agent_ui.end_request()
            self._follow_plan_approval()
            self._update_context_level()

        self.agent_ui.print_footer(response)
        if self.context_provider and response.text:
            self.context_provider.add_to_history(
                "assistant",
                response.text,
                metadata={"mode": self.interaction_mode, "timestamp": time.time()},
            )
        return True

    def _follow_plan_approval(self) -> None:
        """
        The user approved a plan (exit_plan_mode switched the agent out of plan
        mode): leave plan mode here too, so the next request isn't planned again.
        """
        from joshu.core.permissions import PermissionMode

        mode = self.agent.permissions.mode if self.agent is not None else None
        if self.interaction_mode == "plan" and mode not in (None, PermissionMode.PLAN):
            self.interaction_mode = "agent"
            self.config_manager.set("permission_mode", mode.value)

    def _start_background_work(self) -> None:
        """
        Once the prompt is on screen: start the MCP servers and load what the
        first request needs, so neither delays the prompt (the first request
        waits for the MCP servers only if they're still starting).
        """
        if self._background_started:
            return
        self._background_started = True
        from joshu.mcp.startup import load_mcp_tools_in_background

        load_mcp_tools_in_background()
        warm_up_in_background()

    def _move_to_background(self) -> None:
        """Ctrl+B while a shell command runs: it continues in the background."""
        from joshu.tools.shell_tool import request_detach

        request_detach()

    def _submit_while_running(self, line: str) -> bool:
        """
        Enter during a request: `/btw <question>` is answered now; anything else
        is queued and sent when the request ends.
        """
        question = side_question_text(line)
        if question is None:
            self.queued.append(line)
            return True
        if self.agent is None:
            return False
        import threading

        agent, ui = self.agent, self.agent_ui

        def answer() -> None:
            try:
                text = agent.side_question(question)
            except Exception as e:
                text = f"(couldn't answer: {e})"
            ui.show_side_answer(question, text)

        threading.Thread(target=answer, daemon=True).start()
        return True

    def _show_message(self, message: str):
        """Show a message to the user."""
        print(message)

    # ------------------------------------------------------------------ modes

    def current_mode(self) -> str:
        """default, accept_edits, bypass, plan or ask."""
        if self.interaction_mode in ("plan", "ask"):
            return self.interaction_mode
        return str(self.config_manager.get("permission_mode", "default") or "default")

    def cycle_mode(self) -> str:
        """Shift+Tab: default -> accept edits -> plan (-> bypass if started in it)."""
        order = ["default", "accept_edits", "plan"] + (["bypass"] if self._bypass_cycle else [])
        current = self.current_mode()
        following = (
            order[(order.index(current) + 1) % len(order)] if current in order else "default"
        )
        if following == "plan":
            self.interaction_mode = "plan"
        else:
            self.interaction_mode = "agent"
            # For this session only; /permissions <mode> saves it
            self.config_manager.set("permission_mode", following)
        return following

    def status_text(self) -> str:
        """Output of the configured status line command, if any."""
        command = self.config_manager.get("statusline")
        if not command:
            return ""
        context = {
            "model": self.model_label(),
            "cwd": str(Path.cwd()),
            "mode": self.current_mode(),
            "session_id": getattr(self.agent, "session_id", None),
            "theme": self.config_manager.get("theme"),
        }
        return self.statusline.text(command, context)

    def _update_context_level(self) -> None:
        """How full the context window is after the last request (for the bottom bar)."""
        agent = self.agent
        if agent is None:
            self.context_level = None
            return
        from joshu.core.compaction import estimate_tokens

        window = int(getattr(agent, "context_window", 0) or 128000)
        self.context_level = min(100, round(100 * estimate_tokens(agent.messages) / window))

    def activity_text(self) -> str:
        """Todo progress, running background shells and context use, for the bottom bar."""
        parts = []
        from joshu.mcp.startup import mcp_loading

        if mcp_loading():
            parts.append("MCP starting…")
        level = getattr(self, "context_level", None)
        if level is not None and level >= CONTEXT_SHOWN_FROM:
            parts.append(f"context {level}%" + (" · /compact" if level >= 80 else ""))
        queued = len(getattr(self, "queued", []) or [])
        if queued:
            parts.append(f"{queued} queued")
        progress = getattr(self.agent_ui, "todo_progress", None)
        if progress:
            done, total, current = progress
            if done < total:
                parts.append(f"☐ {done}/{total}" + (f" {current}" if current else ""))
        try:
            from joshu.tools.shell_tool import running_background_count

            running = running_background_count()
        except Exception:
            running = 0
        if running:
            parts.append(f"{running} shell{'s' if running != 1 else ''} · ↓ to view")
        agent = getattr(self, "agent", None)
        agents = len(agent.background_running()) if agent is not None else 0
        if agents:
            parts.append(f"{agents} agent{'s' if agents != 1 else ''} working")
        return "  ·  ".join(parts)

    def model_label(self) -> str:
        agent_model = getattr(getattr(self.agent, "client", None), "model", None)
        return str(agent_model or self.model or self.config_manager.get("model") or "")

    def _mode_hint(self) -> str:
        """The mode shown under the input box while a request runs ("" in default mode)."""
        mode = self.current_mode()
        return "" if mode == "default" else MODE_HINTS.get(mode, ("", ""))[0]

    def show_shortcuts(self) -> None:
        self._show_message(SHORTCUTS)

    def start(self):
        """Start the interactive mode."""
        if self.verbose_mode:
            self._show_message("Verbose mode: ON (enabled via -v or --verbose flag)")

        while True:
            try:
                if self.queued:
                    # Sent with Enter while the last request ran: goes now
                    queued = self.queued.pop(0)
                    self._show_message(f"> {queued}")
                    if not self._handle_user_input(queued):
                        break
                    continue
                default, self.type_ahead = self.type_ahead, ""
                user_input = prompt(
                    lambda: prompt_message(vi_normal_mode(), self.multiline_mode),
                    bottom_toolbar=lambda: bottom_toolbar(
                        self.current_mode(),
                        self.model_label(),
                        self.notice,
                        self.status_text(),
                        self.activity_text(),
                    ),
                    placeholder=[("class:placeholder", PLACEHOLDER)],
                    default=default,
                    key_bindings=self.key_bindings,
                    style=self.style,
                    completer=self.command_completer,
                    history=self.prompt_history,
                    multiline=self.multiline_mode,
                    complete_while_typing=True,
                    vi_mode=self.vim_enabled,
                    pre_run=self._start_background_work,
                    # Redraws the bar under the input: background shells and
                    # agents finish while the prompt waits
                    refresh_interval=1.0,
                )

                if not self._handle_user_input(user_input):
                    break

            except KeyboardInterrupt:
                self._show_message("\nExiting...")
                break
            except EOFError:
                break

        if self.agent is not None:
            self.agent.end_session()
        self._show_message("Goodbye!")


def start_interactive_mode(
    model: str,
    sandbox: bool = False,
    verbose: bool = False,
    resume: Optional[str] = None,
    continue_last: bool = False,
):
    """Start the interactive mode, optionally continuing a saved session."""

    interactive_mode = InteractiveMode(model, sandbox, verbose=verbose)
    if resume or continue_last:
        interactive_mode.resume_session(resume)
    interactive_mode.start()
