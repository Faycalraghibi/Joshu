"""Main interactive mode implementation."""

import subprocess
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
from .keybindings import create_key_bindings
from .modes import AskModeHandler
from .prompt import get_prompt, get_style
from .utils import (
    copy_to_clipboard,
    execute_file_content,
    paste_from_clipboard,
)


class InteractiveMode:
    """Main interactive mode with advanced terminal features."""

    def __init__(self, model: str, sandbox: bool = False, verbose: bool = False):
        self.model = model
        self.sandbox = sandbox
        self.config_manager = get_config_manager()

        self.max_history_entries = self.config_manager.get("history_limit", 1000)

        self.context_provider = ContextProvider()

        storage_path = Path.cwd() / "cache" / "joshu_data.json"
        self.prompt_history = JsonHistory(storage_path=storage_path)

        self.vim_mode = "INSERT"
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
        self.command_completer = get_command_completer()

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

    def _navigate_history(self, direction: str):
        """Navigate through command history."""
        if not self.command_history:
            return

        if direction == "up" and self._history_index < len(self.command_history) - 1:
            self._history_index += 1
        elif direction == "down" and self._history_index > -1:
            self._history_index -= 1

        if hasattr(self, "buffer") and self._history_index >= 0:
            self.buffer.text = self.command_history[-(self._history_index + 1)]
        elif hasattr(self, "buffer"):
            self.buffer.text = ""

    def _start_reverse_search(self):
        """Start reverse search mode."""
        if not PROMPT_TOOLKIT_AVAILABLE:
            print("Reverse search not available without prompt_toolkit")
            return

        search_term = prompt(
            [("class:reverse-search", "reverse-search: ")],
            key_bindings=self.key_bindings,
            style=self.style,
        )

        if search_term:
            matches = [cmd for cmd in reversed(self.command_history) if search_term in cmd]
            if hasattr(self, "buffer") and matches:
                self.buffer.text = matches[0]

    def _send_to_background(self, command: str):
        """Send command to background bash."""
        try:
            self.bash_history.append(command)
            subprocess.Popen(
                command, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )
            self._show_message(f"Command sent to background: {command}")
            if hasattr(self, "buffer"):
                self.buffer.text = ""
        except Exception as e:
            self._show_message(f"Error: {str(e)}")

    def _move_cursor(self, direction: str):
        """Move cursor in various directions."""
        if not hasattr(self, "buffer"):
            return

        cursor_pos = self.buffer.cursor_position
        text = self.buffer.text

        if direction == "left" and cursor_pos > 0:
            self.buffer.cursor_position = cursor_pos - 1
        elif direction == "right" and cursor_pos < len(text):
            self.buffer.cursor_position = cursor_pos + 1
        elif direction == "word-forward":
            next_space = text.find(" ", cursor_pos)
            if next_space != -1:
                self.buffer.cursor_position = next_space + 1
        elif direction == "word-backward":
            prev_space = text.rfind(" ", 0, cursor_pos)
            if prev_space != -1:
                self.buffer.cursor_position = prev_space

    def _enter_command_mode(self):
        """Enter Vim command mode."""
        if not PROMPT_TOOLKIT_AVAILABLE:
            return

        command = prompt(":", key_bindings=self.key_bindings, style=self.style)
        if command:
            self._handle_vim_command_mode(command)

    def _handle_vim_command_mode(self, command: str):
        """Handle Vim command mode commands."""
        if command == "w":
            self._show_message("Buffer saved")
        elif command == "q":
            self._show_message("Use Ctrl+D to exit")
        elif command == "wq":
            self._show_message("Buffer saved. Use Ctrl+D to exit")
        elif command.startswith("!"):
            self._handle_bash_command(f"!{command[1:]}")

    def _start_vim_delete(self):
        """Start a Vim delete command."""
        if hasattr(self, "buffer"):
            self.buffer.delete()

    def _start_vim_yank(self):
        """Start a Vim yank command."""
        if hasattr(self, "buffer"):
            if copy_to_clipboard(self.buffer.text):
                self._show_message("Copied to clipboard")

    def _paste_from_clipboard(self):
        """Paste from clipboard."""
        clipboard_text = paste_from_clipboard()
        if clipboard_text and hasattr(self, "buffer"):
            self.buffer.insert_text(clipboard_text)
        elif not clipboard_text:
            self._show_message("Could not paste from clipboard")

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

        try:
            code, out, err = run_command(bash_cmd)
            self.bash_history.append(bash_cmd)
            if out:
                self._show_message(out)
            if err:
                self._show_message(f"Error: {err}")
        except Exception as e:
            self._show_message(f"Error executing command: {str(e)}")

    def _handle_file_injection(self, command: str):
        """Handle file injection with @ prefix."""
        if not command.startswith("@"):
            return

        file_path = command[1:] if not command.startswith("@@") else command[2:]
        line_range = None

        if ":" in file_path:
            file_path, range_spec = file_path.split(":", 1)
            try:
                if "-" in range_spec:
                    start, end = map(int, range_spec.split("-", 1))
                    line_range = (start, end)
                else:
                    line_range = (int(range_spec), int(range_spec))
            except ValueError:
                self._show_message(f"Invalid line range: {range_spec}")
                return

        path = Path(file_path)
        if not path.is_absolute():
            path = Path.cwd() / path

        if not path.exists():
            self._show_message(f"File not found: {path}")
            return

        try:
            with open(path, "r") as f:
                lines = f.readlines()

            if line_range:
                start, end = line_range
                start = max(0, start - 1)
                end = min(len(lines), end)
                content = "".join(lines[start:end])
            else:
                content = "".join(lines)

            if command.startswith("@@"):
                execute_file_content(path, content, self._show_message)
            else:
                if hasattr(self, "buffer"):
                    self.buffer.insert_text(content)
                else:
                    print(content)
                self._show_message(f"Injected content from {path}")
        except Exception as e:
            self._show_message(f"Error reading file: {str(e)}")

    def _execute_command(self, command: str):
        """Execute a shell command."""
        try:
            code, out, err = run_command(command)
            self.bash_history.append(command)
            if out:
                self._show_message(out)
            if err:
                self._show_message(f"Error: {err}")

            if self.context_provider:
                result_message = f"Executed command: {command}"
                if out:
                    result_message += f"\nOutput: {out[:200]}..."
                if err:
                    result_message += f"\nError: {err[:200]}..."
                self.context_provider.add_to_history(
                    "assistant",
                    result_message,
                    metadata={
                        "mode": "default",
                        "command": command,
                        "exit_code": code,
                        "timestamp": time.time(),
                    },
                )
        except Exception as e:
            self._show_message(f"Error executing command: {str(e)}")

    def _handle_user_input(self, user_input: str) -> bool:
        """Handle user input and return True if session should continue."""
        if not user_input:
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
        elif user_input.startswith("@"):
            self._handle_file_injection(user_input)
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

        try:
            response = self.agent.run(user_input)
        except KeyboardInterrupt:
            self._show_message("\nInterrupted.")
            return True
        except LLMError as e:
            self._show_message(f"Model error: {e}")
            return True

        self.agent_ui.print_footer(response)
        if self.context_provider and response.text:
            self.context_provider.add_to_history(
                "assistant",
                response.text,
                metadata={"mode": self.interaction_mode, "timestamp": time.time()},
            )
        return True

    def _show_message(self, message: str):
        """Show a message to the user."""
        print(message)

    def start(self):
        """Start the interactive mode."""
        self._show_message("Interactive Mode started. Type /help for commands.")
        self._show_message(
            f"Current mode: [{self.interaction_mode.upper()}]. Switch modes with /agent, /ask, or /plan"
        )
        if self.verbose_mode:
            self._show_message("Verbose mode: ON (enabled via -v or --verbose flag)")

        while True:
            try:
                user_input = prompt(
                    get_prompt(self.interaction_mode, self.vim_mode, self.multiline_mode),
                    key_bindings=self.key_bindings,
                    style=self.style,
                    completer=self.command_completer,
                    history=self.prompt_history,
                    multiline=self.multiline_mode,
                )

                if not self._handle_user_input(user_input):
                    break

            except KeyboardInterrupt:
                self._show_message("\nExiting...")
                break
            except EOFError:
                break

        self._show_message("Goodbye!")


def start_interactive_mode(
    model: str,
    sandbox: bool = False,
    verbose: bool = False,
    resume: Optional[str] = None,
    continue_last: bool = False,
):
    """Start the interactive mode, optionally continuing a saved session."""
    try:
        from joshu.core.config import get_config_manager

        config_mgr = get_config_manager()

        if config_mgr.get("mcp_enabled", True):
            import asyncio

            from joshu.mcp.discovery import register_mcp_tools_with_joshu
            from joshu.ui.cli_handlers.mcp_handler import load_mcp_servers_from_config

            load_mcp_servers_from_config()

            if config_mgr.get("mcp_discovery_on_startup", True):
                try:
                    count = asyncio.run(register_mcp_tools_with_joshu())
                    if count > 0:
                        print(f"[MCP] Registered {count} tools from MCP servers")
                except Exception as e:
                    if verbose:
                        print(f"[MCP] Tool discovery failed: {e}")
    except Exception as e:
        if verbose:
            print(f"[MCP] Initialization skipped: {e}")

    interactive_mode = InteractiveMode(model, sandbox, verbose=verbose)
    if resume or continue_last:
        interactive_mode.resume_session(resume)
    interactive_mode.start()
