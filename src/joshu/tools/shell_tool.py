"""
Enhanced Shell Command Tool for Joshu CLI.

Provides controlled shell command execution with:
- Interactive and non-interactive modes
- Allowlist/blocklist command restrictions
- Background process support
- Output processing and formatting
"""

from __future__ import annotations

import logging
import os
import subprocess
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
from uuid import uuid4

from joshu.core.tool_registry import register_tool

logger = logging.getLogger(__name__)

# Default configuration
DEFAULT_TIMEOUT = 60
DEFAULT_MAX_OUTPUT = 10000  # Characters


@dataclass
class ShellConfig:
    """Configuration for shell command execution."""

    # Command restrictions
    allowlist: List[str] = field(default_factory=list)
    blocklist: List[str] = field(
        default_factory=lambda: [
            "rm -rf /",
            "rm -rf /*",
            "sudo rm",
            "format",
            "deltree",
            "mkfs",
            ":(){:|:&};:",  # Fork bomb
            "dd if=/dev/zero",
            "shutdown",
            "reboot",
            "halt",
        ]
    )

    # Execution settings
    timeout: int = DEFAULT_TIMEOUT
    max_output: int = DEFAULT_MAX_OUTPUT
    enable_interactive: bool = False
    working_directory: Optional[str] = None

    # Output settings
    strip_colors: bool = False
    use_pager: bool = False


# Global configuration (can be overridden)
_config: ShellConfig = ShellConfig()


def set_shell_config(config: ShellConfig) -> None:
    """Set global shell configuration."""
    global _config
    _config = config


def get_shell_config() -> ShellConfig:
    """Get current shell configuration."""
    return _config


@dataclass
class ProcessInfo:
    """Information about a running background process."""

    process_id: str
    command: str
    pid: int
    started_at: str
    process: subprocess.Popen


# Background process registry
_background_processes: Dict[str, ProcessInfo] = {}


def is_command_allowed(command: str) -> Tuple[bool, str]:
    """
    Check if a command is allowed based on config.

    Args:
        command: Command string to check

    Returns:
        Tuple of (is_allowed, reason)
    """
    config = get_shell_config()

    for blocked in config.blocklist:
        if blocked.lower() in command.lower():
            return False, f"Command contains blocked pattern: {blocked}"

    if not config.allowlist:
        return True, "Allowed by default"

    cmd_base = command.split()[0] if command.split() else ""
    for allowed in config.allowlist:
        if cmd_base == allowed or command.startswith(allowed):
            return True, f"Matched allowlist: {allowed}"

    return False, "Command not in allowlist"


def strip_ansi_codes(text: str) -> str:
    """Remove ANSI escape codes from text."""
    import re

    ansi_escape = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")
    return ansi_escape.sub("", text)


def run_shell_command(
    command: str,
    timeout: Optional[int] = None,
    cwd: Optional[str] = None,
    env: Optional[Dict[str, str]] = None,
    strip_colors: bool = False,
) -> Dict[str, Any]:
    """
    Execute a shell command synchronously.

    Args:
        command: Command string to execute
        timeout: Timeout in seconds
        cwd: Working directory
        env: Environment variables
        strip_colors: Whether to strip ANSI color codes

    Returns:
        Dictionary with execution results
    """
    config = get_shell_config()
    timeout = timeout or config.timeout
    cwd = cwd or config.working_directory

    allowed, reason = is_command_allowed(command)
    if not allowed:
        return {
            "success": False,
            "error": f"Command not allowed: {reason}",
            "exit_code": -1,
        }

    try:
        process_env = os.environ.copy()
        if env:
            process_env.update(env)

        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=cwd,
            env=process_env,
            encoding="utf-8",
            errors="replace",
        )

        stdout = result.stdout
        stderr = result.stderr

        # Strip colors if requested
        if strip_colors or config.strip_colors:
            stdout = strip_ansi_codes(stdout)
            stderr = strip_ansi_codes(stderr)

        # Truncate output if too long
        if len(stdout) > config.max_output:
            stdout = stdout[: config.max_output] + "\n... (truncated)"
        if len(stderr) > config.max_output:
            stderr = stderr[: config.max_output] + "\n... (truncated)"

        return {
            "success": result.returncode == 0,
            "exit_code": result.returncode,
            "stdout": stdout,
            "stderr": stderr,
            "command": command,
        }

    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "error": f"Command timed out after {timeout} seconds",
            "exit_code": -1,
            "command": command,
        }
    except Exception as e:
        logger.error(f"Shell command error: {e}")
        return {
            "success": False,
            "error": str(e),
            "exit_code": -1,
            "command": command,
        }


def start_background_process(
    command: str,
    cwd: Optional[str] = None,
    env: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    """
    Start a command as a background process.

    Args:
        command: Command string to execute
        cwd: Working directory
        env: Environment variables

    Returns:
        Dictionary with process info
    """
    config = get_shell_config()
    cwd = cwd or config.working_directory

    # Check if command is allowed
    allowed, reason = is_command_allowed(command)
    if not allowed:
        return {
            "success": False,
            "error": f"Command not allowed: {reason}",
        }

    try:
        process_env = os.environ.copy()
        if env:
            process_env.update(env)

        process = subprocess.Popen(
            command,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=cwd,
            env=process_env,
            text=True,
        )

        process_id = str(uuid4())[:8]
        info = ProcessInfo(
            process_id=process_id,
            command=command,
            pid=process.pid,
            started_at=datetime.now().isoformat(),
            process=process,
        )
        _background_processes[process_id] = info

        logger.info(f"Started background process {process_id}: {command}")

        return {
            "success": True,
            "process_id": process_id,
            "pid": process.pid,
            "command": command,
            "message": f"Background process started with ID: {process_id}",
        }

    except Exception as e:
        logger.error(f"Failed to start background process: {e}")
        return {
            "success": False,
            "error": str(e),
        }


def get_process_status(process_id: str) -> Dict[str, Any]:
    """
    Get status of a background process.

    Args:
        process_id: Process identifier

    Returns:
        Dictionary with process status
    """
    if process_id not in _background_processes:
        return {
            "success": False,
            "error": f"Process not found: {process_id}",
        }

    info = _background_processes[process_id]
    poll = info.process.poll()

    if poll is None:
        return {
            "success": True,
            "process_id": process_id,
            "status": "running",
            "pid": info.pid,
            "command": info.command,
            "started_at": info.started_at,
        }
    else:
        stdout, stderr = info.process.communicate()
        return {
            "success": True,
            "process_id": process_id,
            "status": "completed",
            "exit_code": poll,
            "stdout": stdout,
            "stderr": stderr,
            "pid": info.pid,
            "command": info.command,
        }


def stop_background_process(process_id: str) -> Dict[str, Any]:
    """
    Stop a background process.

    Args:
        process_id: Process identifier

    Returns:
        Dictionary with stop result
    """
    if process_id not in _background_processes:
        return {
            "success": False,
            "error": f"Process not found: {process_id}",
        }

    info = _background_processes[process_id]

    try:
        info.process.terminate()
        info.process.wait(timeout=5)
        del _background_processes[process_id]

        return {
            "success": True,
            "message": f"Process {process_id} terminated",
        }
    except subprocess.TimeoutExpired:
        info.process.kill()
        del _background_processes[process_id]
        return {
            "success": True,
            "message": f"Process {process_id} killed (did not terminate gracefully)",
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
        }


# Register the tool
@register_tool(
    name="run_shell_command",
    description="""Execute shell commands.

Use this tool to:
- Run build commands (npm, pip, make)
- Execute scripts
- Check system status
- Run tests
- Git operations

Returns stdout, stderr, and exit code.
Some dangerous commands are blocked for safety.

For long-running commands, use background=true to start them in the background.""",
    parameters={
        "type": "object",
        "properties": {
            "command": {
                "type": "string",
                "description": "Shell command to execute",
            },
            "timeout": {
                "type": "integer",
                "description": "Timeout in seconds (default: 60)",
            },
            "working_directory": {
                "type": "string",
                "description": "Directory to run command in",
            },
            "background": {
                "type": "boolean",
                "description": "Run as background process (default: false)",
            },
        },
        "required": ["command"],
    },
    enabled=True,
    requires_approval=True,  # Shell commands require approval
)
def run_shell_command_tool(
    command: str,
    timeout: int = DEFAULT_TIMEOUT,
    working_directory: Optional[str] = None,
    background: bool = False,
) -> Dict[str, Any]:
    """
    Execute a shell command.

    Args:
        command: Command to execute
        timeout: Timeout in seconds
        working_directory: Working directory
        background: Run in background

    Returns:
        Dictionary with execution results
    """
    if not command or not command.strip():
        return {
            "success": False,
            "error": "Empty command provided",
        }

    if background:
        return start_background_process(command, cwd=working_directory)
    else:
        return run_shell_command(command, timeout=timeout, cwd=working_directory)
