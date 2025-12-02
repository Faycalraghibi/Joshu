"""Main interactive mode implementation."""

import os
import subprocess
import time
from pathlib import Path

try:
    from prompt_toolkit.shortcuts import prompt

    PROMPT_TOOLKIT_AVAILABLE = True
except ImportError:
    prompt = None
    PROMPT_TOOLKIT_AVAILABLE = False

from joshu.core.config import get_config_manager
from joshu.core.context_provider import ContextProvider
from joshu.core.safety import assess_command_safety
from joshu.core.translate import translate_to_command
from joshu.tools.shell import run_command

from .commands import CommandHandler
from .completers import get_command_completer, get_path_completer
from .history import JsonHistory
from .keybindings import create_key_bindings
from .modes import AgentModeHandler, AskModeHandler, PlanModeHandler
from .prompt import get_prompt, get_style
from .utils import (
    copy_to_clipboard,
    execute_file_content,
    paste_from_clipboard,
    process_command_substitution,
)

# Conditional imports for OpenAI
try:
    from openai import OpenAI

    OPENAI_AVAILABLE = True
except ImportError:
    OpenAI = None
    OPENAI_AVAILABLE = False


class InteractiveMode:
    """Main interactive mode with advanced terminal features."""

    def __init__(self, model: str, sandbox: bool = False, verbose: bool = False):
        self.model = model
        self.sandbox = sandbox
        self.config_manager = get_config_manager()

        self.max_history_entries = self.config_manager.get("history_limit", 1000)

        # Initialize context provider (uses JSON storage by default)
        self.context_provider = ContextProvider()

        # Initialize JSON-backed prompt history (for prompt_toolkit up/down arrow navigation)
        # Share the same storage backend as context provider for consistency
        storage_path = Path.cwd() / ".joshu_data.json"
        self.prompt_history = JsonHistory(storage_path=storage_path)

        # Mode state
        self.vim_mode = "INSERT"
        self.multiline_mode = False
        self.verbose_mode = verbose
        self.suggestions_enabled = True
        self.interaction_mode = "agent"  # Default to agent mode

        # Set logging level based on verbose mode
        if verbose:
            import logging

            logging.getLogger().setLevel(logging.DEBUG)
            logging.getLogger("joshu").setLevel(logging.DEBUG)
            logging.getLogger("joshu.core").setLevel(logging.DEBUG)
            logging.getLogger("joshu.models").setLevel(logging.DEBUG)

        # History
        self.command_history = []
        self.bash_history = []
        self._history_index = -1

        # Initialize handlers
        self.ask_handler = AskModeHandler(self)
        self.plan_handler = PlanModeHandler(self)
        self.agent_handler = AgentModeHandler(self)
        self.command_handler = CommandHandler(self)

        # DeepSeek API
        self.deepseek_client = None
        self.deepseek_model = os.getenv("DEEPSEEK_URL", "deepseek/deepseek-chat-v3.1:free")
        self.deepseek_auto_exec = os.getenv("DEEPSEEK_AUTO_EXEC", "false").lower() == "true"
        self._init_deepseek()

        # Initialize prompt_toolkit components
        if PROMPT_TOOLKIT_AVAILABLE:
            self._init_prompt_toolkit()

        # Load existing history
        self._load_history()

        # Establish connection
        try:
            from joshu.core.translate import establish_connection

            if establish_connection(self.model):
                self._show_message("Connection established successfully")
            else:
                self._show_message("Failed to establish connection, will retry on first request")
        except Exception as e:
            self._show_message(f"Connection establishment skipped: {e}")

    def _init_deepseek(self):
        """Initialize DeepSeek API client."""
        if OPENAI_AVAILABLE:
            api_key = os.getenv("DEEPSEEK_API_KEY")
            if api_key and OpenAI is not None:
                try:
                    self.deepseek_client = OpenAI(
                        api_key=api_key,
                        base_url="https://openrouter.ai/api/v1",
                        timeout=60.0,  # Add explicit timeout
                        max_retries=2,  # Add explicit retries
                    )
                except Exception as e:
                    # Silently fail if OpenAI client can't be initialized
                    self.deepseek_client = None
                    if self.verbose_mode:
                        print(f"Could not initialize DeepSeek client: {e}")

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
        # Load from prompt history storage
        self.command_history = self.prompt_history.load_history_strings()[
            : self.max_history_entries
        ]

    def _add_to_history(self, command: str):
        """Add command to history."""
        if command and command.strip():
            # Store in prompt history (JSON storage)
            self.prompt_history.store_string(command)
            # Update in-memory list
            if not self.command_history or self.command_history[-1] != command:
                self.command_history.append(command)
                # Keep only last N entries in memory
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

        # Handle special commands
        if user_input.startswith("/"):
            return self.command_handler.handle_slash_command(user_input)
        elif user_input.startswith("!"):
            self._handle_bash_command(user_input)
            return True
        elif user_input.startswith("@"):
            self._handle_file_injection(user_input)
            return True

        # Route to appropriate mode handler
        if self.interaction_mode == "ask":
            return self.ask_handler.handle(user_input)
        elif self.interaction_mode == "plan":
            return self.plan_handler.handle(user_input)
        elif self.interaction_mode == "agent":
            return self.agent_handler.handle(user_input)
        else:
            # Fallback to original behavior
            processed_input = process_command_substitution(user_input)
            translation = translate_to_command(processed_input, self.context_provider, self.model)

            if not translation:
                self._show_message("No translation found. Try rephrasing.")
                return True

            self._show_message(f"Proposed command: {translation.command}")
            self._show_message(f"Explanation: {translation.explanation}")

            needs_execution = getattr(translation, "needs_execution", True)
            explanation_lower = translation.explanation.lower()
            command_normalized = translation.command.replace('\\"', '"').replace("\\'", "'")

            conversational_keywords = [
                "conversational response",
                "direct response",
                "direct answer",
                "to user's query",
                "to user's question",
                "user's query",
                "user's question",
                "answering",
                "providing answer",
                "providing response",
            ]

            is_conversational_explanation = any(
                keyword in explanation_lower for keyword in conversational_keywords
            )
            is_conversational_command = '"""' in command_normalized or (
                command_normalized.startswith('echo "') and len(translation.command) > 100
            )

            if is_conversational_explanation or is_conversational_command:
                needs_execution = False

            if not needs_execution:
                self._execute_command(translation.command)
                return True

            if (
                "code command" in translation.explanation.lower()
                or "code' command" in translation.explanation.lower()
            ):
                self._show_message("💡 Tip: For code generation requests, use the 'code' command:")
                self._show_message(f'   joshu code "{processed_input}"')
                self._show_message(
                    "This will generate the code directly instead of trying to translate to a shell command."
                )
                return True

            report = assess_command_safety(translation.command, self.sandbox)
            if not report.safe:
                self._show_message(f"⚠️  Command blocked for safety: {report.danger_level}")
                for reason in report.reasons:
                    self._show_message(f"  - {reason}")
                if report.suggested_alternative:
                    self._show_message(f"Suggested alternative: {report.suggested_alternative}")
                return True

            auto_execute = self.config_manager.get("auto_execute", False)
            if auto_execute:
                self._execute_command(translation.command)
            else:
                try:
                    confirm = input("Execute this command? [y/N]: ")
                    if confirm.lower() in ["y", "yes"]:
                        self._execute_command(translation.command)
                except EOFError:
                    pass

        return True

    def _show_message(self, message: str):
        """Show a message to the user."""
        print(message)

    def start(self):
        """Start the interactive mode."""
        if not PROMPT_TOOLKIT_AVAILABLE:
            self._show_message(
                "Interactive Mode requires prompt_toolkit. Falling back to basic mode."
            )
            from joshu.ui.cli import start_basic_interactive_mode

            start_basic_interactive_mode(self.model, self.sandbox, self.config_manager)
            return

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


def start_interactive_mode(model: str, sandbox: bool = False, verbose: bool = False):
    """Start the interactive mode."""
    interactive_mode = InteractiveMode(model, sandbox, verbose=verbose)
    interactive_mode.start()
