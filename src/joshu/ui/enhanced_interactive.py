import os
import re
import subprocess
import tempfile
from pathlib import Path
from typing import List, Dict, Optional, Tuple, Any
import json
from datetime import datetime

try:
    import prompt_toolkit
    from prompt_toolkit import Application
    from prompt_toolkit.buffer import Buffer
    from prompt_toolkit.key_binding import KeyBindings
    from prompt_toolkit.layout.containers import HSplit, VSplit, Window, FloatContainer, Float
    from prompt_toolkit.layout.controls import BufferControl, FormattedTextControl
    from prompt_toolkit.layout.layout import Layout
    from prompt_toolkit.styles import Style
    from prompt_toolkit.filters import Condition
    from prompt_toolkit.completion import PathCompleter, WordCompleter
    from prompt_toolkit.history import FileHistory
    from prompt_toolkit.shortcuts import prompt
    PROMPT_TOOLKIT_AVAILABLE = True
except ImportError:
    prompt_toolkit = None
    Application = None
    Buffer = None
    KeyBindings = None
    HSplit = None
    VSplit = None
    Window = None
    FloatContainer = None
    Float = None
    BufferControl = None
    FormattedTextControl = None
    Layout = None
    Style = None
    Condition = None
    PathCompleter = None
    WordCompleter = None
    FileHistory = None
    prompt = None
    PROMPT_TOOLKIT_AVAILABLE = False

from dotenv import load_dotenv

# Conditional imports for OpenAI
try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OpenAI = None
    OPENAI_AVAILABLE = False

from joshu.core.config import get_config_manager
from joshu.core.context_provider import ContextProvider
from joshu.core.safety import assess_command_safety
from joshu.core.translate import translate_to_command
from joshu.tools.shell import run_command

load_dotenv()


class EnhancedInteractiveMode:
    """Enhanced Interactive Mode with advanced terminal features"""
    
    def __init__(self, model: str, sandbox: bool = False):
        self.model = model
        self.sandbox = sandbox
        
        # Get configuration manager
        self.config_manager = get_config_manager()
        
        # Initialize context provider
        self.context_provider = ContextProvider()
        
        # Mode state
        self.vim_mode = 'INSERT'  # NORMAL or INSERT
        self.multiline_mode = False
        self.verbose_mode = False
        self.suggestions_enabled = True
        
        # History
        self.command_history = []
        self.bash_history = []
        self.history_file = Path.cwd() / '.joshu_history'
        self.max_history_entries = self.config_manager.get('history_limit', 1000)
        
        # DeepSeek API
        self.deepseek_client = None
        self.deepseek_model = os.getenv('DEEPSEEK_URL', 'deepseek/deepseek-chat-v3.1:free')
        self.deepseek_auto_exec = os.getenv('DEEPSEEK_AUTO_EXEC', 'false').lower() == 'true'
        self._init_deepseek()
        
        # Initialize prompt_toolkit components
        if PROMPT_TOOLKIT_AVAILABLE:
            self._init_prompt_toolkit()
        
        # Load existing history
        self._load_history()
    
    def _init_deepseek(self):
        """Initialize DeepSeek API client"""
        if OPENAI_AVAILABLE:
            api_key = os.getenv('DEEPSEEK_API_KEY')
            if api_key and OpenAI is not None:
                self.deepseek_client = OpenAI(
                    api_key=api_key,
                    base_url="https://openrouter.ai/api/v1"
                )

    def _init_prompt_toolkit(self):
        """Initialize prompt_toolkit components"""
        if not PROMPT_TOOLKIT_AVAILABLE:
            return
            
        self.key_bindings = KeyBindings()
        self._setup_key_bindings()
        
        self.style = Style.from_dict({
            'prompt': '#00aa00 bold',
            'normal-mode': '#0000aa bold',
            'multiline': '#aa0000 bold',
            'reverse-search': '#aaaa00 bold',
            'bash-command': '#aa00aa',
            'file-injection': '#00aaaa',
        })
        
        self.path_completer = PathCompleter()
        self.command_completer = WordCompleter([
            'ls', 'cd', 'pwd', 'find', 'grep', 'cat', 'less', 'head', 'tail',
            'cp', 'mv', 'rm', 'mkdir', 'rmdir', 'chmod', 'chown',
            'git', 'docker', 'pip', 'npm', 'yarn', 'python', 'node'
        ], ignore_case=True)
    
    def _setup_key_bindings(self):
        """Setup keyboard shortcuts"""
        if not PROMPT_TOOLKIT_AVAILABLE:
            return
            
        @self.key_bindings.add('c-j')
        def _(event):
            """Ctrl+J for line navigation down"""
            if self.vim_mode == 'NORMAL':
                self._navigate_history('down')
        
        @self.key_bindings.add('c-k')
        def _(event):
            """Ctrl+K for line navigation up"""
            if self.vim_mode == 'NORMAL':
                self._navigate_history('up')
        
        @self.key_bindings.add('c-r')
        def _(event):
            """Ctrl+R for reverse search"""
            self._start_reverse_search()
        
        @self.key_bindings.add('c-b')
        def _(event):
            """Ctrl+B to send command to background bash"""
            if hasattr(self, 'buffer') and self.buffer.text:
                self._send_to_background(self.buffer.text)
        
        @self.key_bindings.add('c-c')
        def _(event):
            """Ctrl+C for graceful interrupt"""
            event.app.exit(exception=KeyboardInterrupt)
        
        @self.key_bindings.add('c-d')
        def _(event):
            """Ctrl+D for exit"""
            if not hasattr(self, 'buffer') or not self.buffer.text:
                event.app.exit()
        
        @self.key_bindings.add('c-l')
        def _(event):
            """Ctrl+L for clear screen"""
            subprocess.run('clear' if os.name != 'nt' else 'cls', shell=True)
        
        @self.key_bindings.add('c-v')
        def _(event):
            """Ctrl+V for verbose toggle"""
            self.verbose_mode = not self.verbose_mode
            self._show_message(f"Verbose mode: {'ON' if self.verbose_mode else 'OFF'}")
        
        @self.key_bindings.add('c-t')
        def _(event):
            """Ctrl+T for command suggestion toggle"""
            self.suggestions_enabled = not self.suggestions_enabled
            self._show_message(f"Command suggestions: {'ON' if self.suggestions_enabled else 'OFF'}")
        
        @self.key_bindings.add('escape')
        def _(event):
            """Escape key to switch to NORMAL mode"""
            self.vim_mode = 'NORMAL'
        
        # Vim-style navigation in NORMAL mode
        @self.key_bindings.add('h', filter=Condition(lambda: self.vim_mode == 'NORMAL'))
        def _(event):
            """Vim 'h' for left"""
            self._move_cursor('left')
        
        @self.key_bindings.add('l', filter=Condition(lambda: self.vim_mode == 'NORMAL'))
        def _(event):
            """Vim 'l' for right"""
            self._move_cursor('right')
        
        @self.key_bindings.add('j', filter=Condition(lambda: self.vim_mode == 'NORMAL'))
        def _(event):
            """Vim 'j' for down"""
            self._navigate_history('down')
        
        @self.key_bindings.add('k', filter=Condition(lambda: self.vim_mode == 'NORMAL'))
        def _(event):
            """Vim 'k' for up"""
            self._navigate_history('up')
        
        @self.key_bindings.add('w', filter=Condition(lambda: self.vim_mode == 'NORMAL'))
        def _(event):
            """Vim 'w' for word forward"""
            self._move_cursor('word-forward')
        
        @self.key_bindings.add('b', filter=Condition(lambda: self.vim_mode == 'NORMAL'))
        def _(event):
            """Vim 'b' for word backward"""
            self._move_cursor('word-backward')
        
        @self.key_bindings.add('i', filter=Condition(lambda: self.vim_mode == 'NORMAL'))
        def _(event):
            """Vim 'i' to enter INSERT mode"""
            self.vim_mode = 'INSERT'
        
        @self.key_bindings.add('a', filter=Condition(lambda: self.vim_mode == 'NORMAL'))
        def _(event):
            """Vim 'a' to append after cursor"""
            self.vim_mode = 'INSERT'
            self._move_cursor('right')
        
        @self.key_bindings.add(':', filter=Condition(lambda: self.vim_mode == 'NORMAL'))
        def _(event):
            """Vim ':' for command mode"""
            self._enter_command_mode()
        
        # Vim editing commands
        @self.key_bindings.add('d', filter=Condition(lambda: self.vim_mode == 'NORMAL'))
        def _(event):
            """Start of delete command"""
            self._start_vim_delete()
        
        @self.key_bindings.add('y', filter=Condition(lambda: self.vim_mode == 'NORMAL'))
        def _(event):
            """Start of yank command"""
            self._start_vim_yank()
        
        @self.key_bindings.add('p', filter=Condition(lambda: self.vim_mode == 'NORMAL'))
        def _(event):
            """Vim 'p' to paste"""
            self._paste_from_clipboard()
    
    def _get_prompt(self) -> list:
        """Get the current prompt based on mode"""
        if not PROMPT_TOOLKIT_AVAILABLE:
            return "$ "
            
        mode_indicator = self.vim_mode[0] if self.vim_mode == 'NORMAL' else ''
        multiline_indicator = '>' if self.multiline_mode else '$'
        
        if self.vim_mode == 'NORMAL':
            return [('class:normal-mode', f'NORMAL {mode_indicator} {multiline_indicator} ')]
        elif self.multiline_mode:
            return [('class:multiline', f'MULTILINE {multiline_indicator} ')]
        else:
            return [('class:prompt', f'{mode_indicator}{multiline_indicator} ')]
    
    def _load_history(self):
        """Load command history from file"""
        if self.history_file.exists():
            try:
                with open(self.history_file, 'r') as f:
                    self.command_history = [line.strip() for line in f.readlines()]
                    self.command_history = self.command_history[-int(self.max_history_entries):]
            except (json.JSONDecodeError, IOError):
                self.command_history = []
    
    def _save_history(self):
        """Save command history to file"""
        try:
            with open(self.history_file, 'w') as f:
                for cmd in self.command_history[-self.max_history_entries:]:
                    f.write(f"{cmd}\n")
        except IOError:
            pass
    
    def _add_to_history(self, command: str):
        """Add command to history"""
        if command and (not self.command_history or command != self.command_history[-1]):
            self.command_history.append(command)
            self._save_history()
    
    def _navigate_history(self, direction: str):
        """Navigate through command history"""
        if not self.command_history:
            return
        
        current_index = getattr(self, '_history_index', -1)
        
        if direction == 'up' and current_index < len(self.command_history) - 1:
            current_index += 1
        elif direction == 'down' and current_index > -1:
            current_index -= 1
        
        self._history_index = current_index
        
        if hasattr(self, 'buffer') and current_index >= 0:
            self.buffer.text = self.command_history[-(current_index + 1)]
        elif hasattr(self, 'buffer'):
            self.buffer.text = ""
    
    def _start_reverse_search(self):
        """Start reverse search mode"""
        if not PROMPT_TOOLKIT_AVAILABLE:
            print("Reverse search not available without prompt_toolkit")
            return
            
        search_term = prompt(
            [('class:reverse-search', 'reverse-search: ')],
            key_bindings=self.key_bindings,
            style=self.style
        )
        
        if search_term:
            matches = [cmd for cmd in reversed(self.command_history) if search_term in cmd]
            if hasattr(self, 'buffer') and matches:
                self.buffer.text = matches[0]
    
    def _send_to_background(self, command: str):
        """Send command to background bash"""
        try:
            # Add to bash history
            self.bash_history.append(command)
            
            # Execute in background
            subprocess.Popen(command, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            self._show_message(f"Command sent to background: {command}")
            
            # Clear buffer
            if hasattr(self, 'buffer'):
                self.buffer.text = ""
        except Exception as e:
            self._show_message(f"Error: {str(e)}")
    
    def _move_cursor(self, direction: str):
        """Move cursor in various directions"""
        if not hasattr(self, 'buffer'):
            return
            
        cursor_pos = self.buffer.cursor_position
        text = self.buffer.text
        
        if direction == 'left' and cursor_pos > 0:
            self.buffer.cursor_position = cursor_pos - 1
        elif direction == 'right' and cursor_pos < len(text):
            self.buffer.cursor_position = cursor_pos + 1
        elif direction == 'word-forward':
            # Find next word boundary
            next_space = text.find(' ', cursor_pos)
            if next_space != -1:
                self.buffer.cursor_position = next_space + 1
        elif direction == 'word-backward':
            # Find previous word boundary
            prev_space = text.rfind(' ', 0, cursor_pos)
            if prev_space != -1:
                self.buffer.cursor_position = prev_space
    
    def _enter_command_mode(self):
        """Enter Vim command mode"""
        if not PROMPT_TOOLKIT_AVAILABLE:
            return
            
        command = prompt(
            ':',
            key_bindings=self.key_bindings,
            style=self.style
        )
        
        if command:
            self._handle_vim_command_mode(command)
    
    def _handle_vim_command_mode(self, command: str):
        """Handle Vim command mode commands"""
        if command == 'w':
            # Save current buffer (in our context, just show a message)
            self._show_message("Buffer saved")
        elif command == 'q':
            # Quit
            self._show_message("Use Ctrl+D to exit")
        elif command == 'wq':
            # Save and quit
            self._show_message("Buffer saved. Use Ctrl+D to exit")
        elif command.startswith('!'):
            # Execute shell command
            shell_cmd = command[1:]
            self._handle_bash_command(f"!{shell_cmd}")
    
    def _start_vim_delete(self):
        """Start a Vim delete command"""
        # This is a simplified implementation
        # In a full implementation, we'd wait for the next key to determine what to delete
        if hasattr(self, 'buffer'):
            self.buffer.delete()
    
    def _start_vim_yank(self):
        """Start a Vim yank command"""
        # This is a simplified implementation
        # In a full implementation, we'd wait for the next key to determine what to yank
        if hasattr(self, 'buffer'):
            self._copy_to_clipboard(self.buffer.text)
    
    def _copy_to_clipboard(self, text: str):
        """Copy text to clipboard"""
        try:
            if os.name == 'nt':
                # Windows
                subprocess.run(['clip'], input=text, text=True, check=True)
            else:
                # Unix-like
                subprocess.run(['pbcopy'], input=text, text=True, check=True)
            self._show_message("Copied to clipboard")
        except (subprocess.SubprocessError, FileNotFoundError):
            self._show_message("Could not copy to clipboard")
    
    def _paste_from_clipboard(self):
        """Paste from clipboard"""
        try:
            if os.name == 'nt':
                # Windows
                result = subprocess.run(['powershell', '-command', 'Get-Clipboard'], 
                                      capture_output=True, text=True, check=True)
            else:
                # Unix-like
                result = subprocess.run(['pbpaste'], capture_output=True, text=True, check=True)
            
            clipboard_text = result.stdout.strip()
            if hasattr(self, 'buffer'):
                self.buffer.insert_text(clipboard_text)
        except (subprocess.SubprocessError, FileNotFoundError):
            self._show_message("Could not paste from clipboard")
    
    def _handle_bash_command(self, command: str):
        """Handle bash command with ! prefix"""
        if not command.startswith('!'):
            return
        
        bash_cmd = command[1:]
        
        # Handle special cases
        if bash_cmd == '!':
            # Repeat last bash command
            if self.bash_history:
                bash_cmd = self.bash_history[-1]
            else:
                self._show_message("No bash command history")
                return
        elif bash_cmd.startswith('!'):
            # Execute nth command from history
            try:
                n = int(bash_cmd[1:])
                if 0 < n <= len(self.bash_history):
                    bash_cmd = self.bash_history[n-1]
                else:
                    self._show_message(f"Invalid bash command number: {n}")
                    return
            except ValueError:
                # Pattern matching
                pattern = bash_cmd[1:]
                matches = [cmd for cmd in self.bash_history if pattern in cmd]
                if matches:
                    bash_cmd = matches[-1]
                else:
                    self._show_message(f"No bash command matching: {pattern}")
                    return
        
        # Execute command
        try:
            code, out, err = run_command(bash_cmd)
            
            # Add to bash history
            self.bash_history.append(bash_cmd)
            
            # Display result
            if out:
                self._show_message(out)
            if err:
                self._show_message(f"Error: {err}")
        except Exception as e:
            self._show_message(f"Error executing command: {str(e)}")
    
    def _handle_file_injection(self, command: str):
        """Handle file injection with @ prefix"""
        if not command.startswith('@'):
            return
        
        file_path = command[1:]
        line_range = None
        
        # Check for line range specification
        if ':' in file_path:
            file_path, range_spec = file_path.split(':', 1)
            try:
                if '-' in range_spec:
                    start, end = map(int, range_spec.split('-', 1))
                    line_range = (start, end)
                else:
                    line_range = (int(range_spec), int(range_spec))
            except ValueError:
                self._show_message(f"Invalid line range: {range_spec}")
                return
        
        # Resolve file path
        path = Path(file_path)
        if not path.is_absolute():
            path = Path.cwd() / path
        
        # Check if file exists
        if not path.exists():
            self._show_message(f"File not found: {path}")
            return
        
        try:
            # Read file content
            with open(path, 'r') as f:
                lines = f.readlines()
            
            # Apply line range if specified
            if line_range:
                start, end = line_range
                # Adjust for 0-based indexing
                start = max(0, start - 1)
                end = min(len(lines), end)
                content = ''.join(lines[start:end])
            else:
                content = ''.join(lines)
            
            # Check for double @ (execute)
            if command.startswith('@@'):
                # Execute the file content
                self._execute_file_content(path, content)
            else:
                # Insert content into buffer or print it
                if hasattr(self, 'buffer'):
                    self.buffer.insert_text(content)
                else:
                    print(content)
                self._show_message(f"Injected content from {path}")
        except Exception as e:
            self._show_message(f"Error reading file: {str(e)}")
    
    def _execute_file_content(self, path: Path, content: str):
        """Execute file content"""
        # Determine file type and execute accordingly
        extension = path.suffix.lower()
        
        if extension == '.sh':
            # Shell script
            with tempfile.NamedTemporaryFile(mode='w', suffix='.sh', delete=False) as f:
                f.write(content)
                temp_path = f.name
            
            try:
                os.chmod(temp_path, 0o755)
                code, out, err = run_command(temp_path)
                
                if out:
                    self._show_message(out)
                if err:
                    self._show_message(f"Error: {err}")
            finally:
                os.unlink(temp_path)
        elif extension == '.py':
            # Python script
            with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
                f.write(content)
                temp_path = f.name
            
            try:
                code, out, err = run_command(f'python {temp_path}')
                
                if out:
                    self._show_message(out)
                if err:
                    self._show_message(f"Error: {err}")
            finally:
                os.unlink(temp_path)
        else:
            self._show_message(f"Cannot execute files of type: {extension}")
    
    def _handle_slash_command(self, command: str) -> bool:
        """Handle slash commands and return True if session should continue"""
        if command == '/clear':
            self.command_history.clear()
            self._save_history()
            self._show_message("Command history cleared")
            return True
        elif command == '/history':
            self._display_history()
            return True
        elif command.startswith('/help'):
            self._show_help()
            return True
        elif command.startswith('/config'):
            self._handle_config_command(command)
            return True
        elif command.startswith('/model'):
            self._handle_model_command(command)
            return True
        else:
            self._show_message(f"Unknown command: {command}")
            return True
    
    def _display_history(self):
        """Display command history"""
        if not self.command_history:
            self._show_message("No command history")
            return
        
        self._show_message("Command History:")
        for i, cmd in enumerate(self.command_history[-20:], 1):
            self._show_message(f"{i}: {cmd}")
    
    def _show_help(self):
        """Display help information"""
        help_text = """
Enhanced Interactive Mode Help:

Keyboard Shortcuts:
  Ctrl+R    - Reverse search
  Ctrl+J    - Line navigation down
  Ctrl+K    - Line navigation up
  Ctrl+B    - Send command to background bash
  Ctrl+C    - Interrupt current operation
  Ctrl+D    - Exit
  Ctrl+L    - Clear screen
  Ctrl+V    - Toggle verbose mode
  Ctrl+T    - Toggle command suggestions

Vim Mode:
  ESC       - Switch to NORMAL mode
  i         - Switch to INSERT mode
  h/j/k/l   - Left/Down/Up/Right
  w/b       - Word forward/backward
  :         - Command mode

Special Commands:
  !command  - Execute bash command
  !!        - Repeat last bash command
  !n        - Execute nth bash command from history
  @file     - Inject file content
  @@file    - Inject and execute file content
  @file:n-m - Inject lines n to m from file
  /clear    - Clear command history
  /history  - Show command history
  /help     - Show this help
  /config   - Show/set configuration
  /model    - Switch AI model
        """
        self._show_message(help_text)
    
    def _handle_config_command(self, command: str):
        """Handle configuration commands"""
        parts = command.split()
        if len(parts) == 1:
            # Show all config
            config_dict = self.config_manager.config.to_dict()
            config_str = json.dumps(config_dict, indent=2)
            self._show_message(config_str)
        elif len(parts) == 2:
            # Get specific config value
            key = parts[1]
            value = self.config_manager.get(key)
            self._show_message(f"{key}: {value}")
        elif len(parts) == 3:
            # Set config value
            key, value = parts[1], parts[2]
            # Try to convert value to appropriate type
            if value.lower() in ("true", "false"):
                value = value.lower() == "true"
            elif value.isdigit():
                value = int(value)
            elif value.replace(".", "").isdigit():
                value = float(value)
            
            if self.config_manager.set(key, value):
                self.config_manager.save_config()
                self._show_message(f"Set {key} = {value}")
            else:
                self._show_message(f"Invalid configuration key: {key}")
    
    def _handle_model_command(self, command: str):
        """Handle model switching commands"""
        parts = command.split()
        if len(parts) == 1:
            # Show current model
            current_model = self.config_manager.get("model", "llama-3-8b")
            self._show_message(f"Current model: {current_model}")
        elif len(parts) == 2:
            # Switch model
            model = parts[1]
            if self.config_manager.set("model", model):
                self.config_manager.save_config()
                self.model = model
                self._show_message(f"Switched to model: {model}")
            else:
                self._show_message(f"Failed to switch to model: {model}")
    
    def _show_message(self, message: str):
        """Show a message to the user"""
        print(message)
    
    def _process_command_substitution(self, command: str) -> str:
        """Process command substitution with backticks"""
        # Find all backtick expressions
        pattern = r'`([^`]*)`'
        matches = re.findall(pattern, command)
        
        for sub_cmd in matches:
            try:
                code, out, err = run_command(sub_cmd)
                if code == 0:
                    output = out.strip()
                    command = command.replace(f'`{sub_cmd}`', output)
            except Exception:
                pass
        
        return command
    
    def _get_file_completions(self, text: str) -> List[str]:
        """Get file completions for @ prefix"""
        if not text.startswith('@'):
            return []
        
        path_text = text[1:]
        path = Path(path_text)
        
        if not path.is_absolute():
            path = Path.cwd() / path
        
        if path.is_dir():
            return [str(p) for p in path.iterdir()]
        else:
            parent = path.parent
            if parent.exists():
                prefix = path.name
                return [str(p) for p in parent.iterdir() if p.name.startswith(prefix)]
        
        return []
    
    def _ask_deepseek(self, prompt: str) -> str:
        """Ask DeepSeek API for assistance"""
        if not self.deepseek_client:
            return "DeepSeek API not available"
        
        try:
            response = self.deepseek_client.chat.completions.create(
                model=self.deepseek_model,
                messages=[
                    {"role": "system", "content": "You are a helpful CLI assistant. Provide concise, accurate shell commands or explanations."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                max_tokens=500
            )
            return response.choices[0].message.content
        except Exception as e:
            return f"Error communicating with DeepSeek: {str(e)}"
    
    def _handle_user_input(self, user_input: str) -> bool:
        """Handle user input and return True if session should continue"""
        if not user_input:
            return True
        
        # Add to history
        self._add_to_history(user_input)
        
        # Update context
        if self.context_provider:
            self.context_provider.add_to_history("user", user_input)
        
        # Handle special commands
        if user_input.startswith('/'):
            return self._handle_slash_command(user_input)
        elif user_input.startswith('!'):
            self._handle_bash_command(user_input)
            return True
        elif user_input.startswith('@'):
            self._handle_file_injection(user_input)
            return True
        
        # Process command substitution
        processed_input = self._process_command_substitution(user_input)
        
        # Use existing translation system
        from joshu.core.translate import translate_to_command
        translation = translate_to_command(processed_input, self.context_provider, self.model)
        
        if translation:
            self._show_message(f"Proposed command: {translation.command}")
            self._show_message(f"Explanation: {translation.explanation}")
            
            # Check if this is a code generation request that should use the code command
            if "code command" in translation.explanation.lower() or "code' command" in translation.explanation.lower():
                self._show_message("💡 Tip: For code generation requests, use the 'code' command:")
                self._show_message(f"   joshu code \"{processed_input}\"")
                self._show_message("This will generate the code directly instead of trying to translate to a shell command.")
                return True
            
            # Check safety
            report = assess_command_safety(translation.command, self.sandbox)
            
            if not report.safe:
                self._show_message(f"⚠️  Command blocked for safety: {report.danger_level}")
                for reason in report.reasons:
                    self._show_message(f"  - {reason}")
                if report.suggested_alternative:
                    self._show_message(f"Suggested alternative: {report.suggested_alternative}")
                return True
            
            # Auto-execute if enabled
            auto_execute = self.config_manager.get("auto_execute", False)
            if auto_execute:
                self._execute_command(translation.command)
            else:
                # Ask for confirmation
                try:
                    confirm = input("Execute this command? [y/N]: ")
                    if confirm.lower() in ['y', 'yes']:
                        self._execute_command(translation.command)
                except EOFError:
                    pass
        else:
            self._show_message("No translation found. Try rephrasing.")
        
        return True
    
    def _execute_command(self, command: str):
        """Execute a shell command"""
        try:
            code, out, err = run_command(command)
            
            # Add to bash history
            self.bash_history.append(command)
            
            # Display result
            if out:
                self._show_message(out)
            if err:
                self._show_message(f"Error: {err}")
            
            # Update context with result
            if self.context_provider:
                self.context_provider.update_context_from_response(
                    f"Executed command: {command}", 
                    f"Output: {out[:100]}..." if out else "No output"
                )
        except Exception as e:
            self._show_message(f"Error executing command: {str(e)}")
    
    def start(self):
        """Start the enhanced interactive mode"""
        if not PROMPT_TOOLKIT_AVAILABLE:
            self._show_message("Enhanced Interactive Mode requires prompt_toolkit. Falling back to basic mode.")
            # Fall back to basic interactive mode
            from joshu.ui.cli import start_basic_interactive_mode
            config_manager = get_config_manager()
            start_basic_interactive_mode(self.model, self.sandbox, config_manager)
            return
            
        self._show_message("Enhanced Interactive Mode started. Type /help for commands.")
        
        while True:
            try:
                # Get user input
                user_input = prompt(
                    self._get_prompt(),
                    key_bindings=self.key_bindings,
                    style=self.style,
                    completer=self.command_completer,
                    history=FileHistory(str(self.history_file)),
                    multiline=self.multiline_mode
                )
                
                # Handle user input
                if not self._handle_user_input(user_input):
                    break
                    
            except KeyboardInterrupt:
                # Allow user to exit with Ctrl+C as well
                self._show_message("\nExiting...")
                break
            except EOFError:
                break
        
        self._show_message("Goodbye!")


# Integration with existing CLI
def start_enhanced_interactive_mode(model: str, sandbox: bool = False, config_manager=None):
    """Start the enhanced interactive mode"""
    enhanced_mode = EnhancedInteractiveMode(model, sandbox)
    enhanced_mode.start()
