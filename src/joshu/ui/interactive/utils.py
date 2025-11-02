"""Utility functions for interactive mode."""

import os
import re
import subprocess
import tempfile
from pathlib import Path
from typing import List

from joshu.tools.shell import run_command

try:
    from prompt_toolkit.shortcuts import prompt
    PROMPT_TOOLKIT_AVAILABLE = True
except ImportError:
    prompt = None
    PROMPT_TOOLKIT_AVAILABLE = False


def load_command_history(history_file: Path, max_entries: int) -> List[str]:
    """Load command history from file."""
    command_history = []
    if history_file.exists():
        try:
            with open(history_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                for line in lines:
                    line = line.strip()
                    if line.startswith('[') and ']' in line:
                        cmd = line.split(']', 1)[1].strip()
                        if cmd and cmd not in command_history:
                            command_history.append(cmd)
                command_history = command_history[-int(max_entries):]
        except (IOError, UnicodeDecodeError):
            pass
    return command_history


def process_command_substitution(command: str) -> str:
    """Process command substitution with backticks."""
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


def copy_to_clipboard(text: str) -> bool:
    """Copy text to clipboard."""
    try:
        if os.name == 'nt':
            subprocess.run(['clip'], input=text, text=True, check=True)
        else:
            subprocess.run(['pbcopy'], input=text, text=True, check=True)
        return True
    except (subprocess.SubprocessError, FileNotFoundError):
        return False


def paste_from_clipboard() -> str:
    """Paste from clipboard."""
    try:
        if os.name == 'nt':
            result = subprocess.run(['powershell', '-command', 'Get-Clipboard'],
                                  capture_output=True, text=True, check=True)
        else:
            result = subprocess.run(['pbpaste'], capture_output=True, text=True, check=True)
        return result.stdout.strip()
    except (subprocess.SubprocessError, FileNotFoundError):
        return ""


def execute_file_content(path: Path, content: str, show_message: callable):
    """Execute file content based on file type."""
    extension = path.suffix.lower()
    
    if extension == '.sh':
        with tempfile.NamedTemporaryFile(mode='w', suffix='.sh', delete=False) as f:
            f.write(content)
            temp_path = f.name
        
        try:
            os.chmod(temp_path, 0o755)
            code, out, err = run_command(temp_path)
            if out:
                show_message(out)
            if err:
                show_message(f"Error: {err}")
        finally:
            os.unlink(temp_path)
    elif extension == '.py':
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(content)
            temp_path = f.name
        
        try:
            code, out, err = run_command(f'python {temp_path}')
            if out:
                show_message(out)
            if err:
                show_message(f"Error: {err}")
        finally:
            os.unlink(temp_path)
    else:
        show_message(f"Cannot execute files of type: {extension}")

