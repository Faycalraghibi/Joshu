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
import re
import subprocess
import tempfile
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
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

    # OS-level sandbox (joshu.core.sandbox.Sandbox) commands are wrapped in
    sandbox: Optional[Any] = None


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
    # stdout and stderr go to this file, so output can be read while it runs
    log_path: Optional[Path] = None
    read_offset: int = 0


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
        if _matches_blocked(command, blocked):
            return False, f"Command contains blocked pattern: {blocked}"

    if not config.allowlist:
        return True, "Allowed by default"

    cmd_base = command.split()[0] if command.split() else ""
    for allowed in config.allowlist:
        if cmd_base == allowed or command.startswith(allowed):
            return True, f"Matched allowlist: {allowed}"

    return False, "Command not in allowlist"


def _command_names(command: str) -> List[str]:
    """Program name of each segment of a command line (split on ; & | and newlines)."""
    names = []
    for segment in re.split(r"[;&|\n]+", command):
        tokens = segment.strip().lstrip("(").split()
        while tokens and tokens[0].lower() in ("sudo", "exec", "nohup", "time"):
            tokens = tokens[1:]
        if tokens:
            name = re.split(r"[\\/]", tokens[0])[-1].lower()
            names.append(name[:-4] if name.endswith(".exe") else name)
    return names


def _matches_blocked(command: str, blocked: str) -> bool:
    """
    Match a blocklist entry against a command line.

    Single words ("format", "shutdown") match only as the program being run, so
    `ruff format` and `git log --format=...` are allowed. Phrases ("rm -rf /")
    match at word boundaries, so `rm -rf /tmp/build` is not caught by "rm -rf /".
    """
    blocked = blocked.strip().lower()
    if not blocked:
        return False

    if " " not in blocked and re.fullmatch(r"[\w.-]+", blocked):
        return any(
            name == blocked or name.startswith(blocked + ".") for name in _command_names(command)
        )

    pattern = r"(?:^|(?<=[\s;&|(]))" + re.escape(blocked)
    if blocked[-1].isalnum() or blocked[-1] == "/":
        pattern += r"(?=$|[\s;&|)])"
    return re.search(pattern, command.lower()) is not None


def set_shell_sandbox(sandbox: Optional[Any]) -> None:
    """Run every shell command through `sandbox` (None: run directly)."""
    get_shell_config().sandbox = sandbox


def _sandboxed(command: str, cwd: Optional[str]) -> str:
    """The command line to execute: wrapped in the sandbox when one is set."""
    sandbox = get_shell_config().sandbox
    if sandbox is None:
        return command
    from pathlib import Path

    return sandbox.wrap(command, Path(cwd) if cwd else None)


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
            _sandboxed(command, cwd),
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

        process_id = str(uuid4())[:8]
        log_path = Path(tempfile.gettempdir()) / f"joshu-bg-{process_id}.log"
        with open(log_path, "wb") as log:
            process = subprocess.Popen(
                _sandboxed(command, cwd),
                shell=True,
                stdout=log,
                stderr=subprocess.STDOUT,
                stdin=subprocess.DEVNULL,
                cwd=cwd,
                env=process_env,
            )

        info = ProcessInfo(
            process_id=process_id,
            command=command,
            pid=process.pid,
            started_at=datetime.now().isoformat(),
            process=process,
            log_path=log_path,
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
    result: Dict[str, Any] = {
        "success": True,
        "process_id": process_id,
        "status": "running" if poll is None else "completed",
        "pid": info.pid,
        "command": info.command,
        "started_at": info.started_at,
        "output": read_process_output(info),
    }
    if poll is not None:
        result["exit_code"] = poll
    return result


def read_process_output(info: ProcessInfo, new_only: bool = True, limit: int = 20000) -> str:
    """Output written by a background process (since the last read when new_only)."""
    if info.log_path is None or not info.log_path.is_file():
        return ""
    data = info.log_path.read_bytes()
    start = info.read_offset if new_only else 0
    chunk = data[start:]
    info.read_offset = len(data)
    text = strip_ansi_codes(chunk.decode("utf-8", errors="replace"))
    if len(text) > limit:
        text = "[... earlier output omitted]\n" + text[-limit:]
    return text


def peek_process_output(info: ProcessInfo, limit: int = 65536) -> str:
    """The end of a background process's output, without moving the agent's read offset."""
    if info.log_path is None or not info.log_path.is_file():
        return ""
    with open(info.log_path, "rb") as log:
        log.seek(0, 2)
        size = log.tell()
        log.seek(max(0, size - limit))
        data = log.read()
    return strip_ansi_codes(data.decode("utf-8", errors="replace"))


def running_background_count() -> int:
    """Background processes still running."""
    return sum(1 for p in _background_processes.values() if p.process.poll() is None)


def list_background_processes() -> List[ProcessInfo]:
    """Background processes started in this session, oldest first."""
    return list(_background_processes.values())


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
    if info.process.poll() is not None:
        del _background_processes[process_id]
        return {"success": True, "message": f"Process {process_id} had already finished"}

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
    description="Run a shell command; returns stdout, stderr and exit code. Use background=true for long-running commands (servers, watchers), then bash_output to read their output. The user may be asked to approve.",
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


@register_tool(
    name="bash_output",
    description="Read new output, status and exit code of a background command.",
    parameters={
        "type": "object",
        "properties": {
            "process_id": {
                "type": "string",
                "description": "The process_id returned when the command was started",
            }
        },
        "required": ["process_id"],
    },
    enabled=True,
    requires_approval=False,
)
def bash_output_tool(process_id: str) -> Dict[str, Any]:
    return get_process_status(process_id)


@register_tool(
    name="kill_bash",
    description="Stop a command started with run_shell_command(background=true).",
    parameters={
        "type": "object",
        "properties": {
            "process_id": {
                "type": "string",
                "description": "The process_id returned when the command was started",
            }
        },
        "required": ["process_id"],
    },
    enabled=True,
    requires_approval=False,
)
def kill_bash_tool(process_id: str) -> Dict[str, Any]:
    return stop_background_process(process_id)
