"""
TOML-Based Custom Commands for Extensions.

Parses and executes custom commands defined in TOML files
within extension's commands/ directory.
"""

from __future__ import annotations

import logging
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Try to import tomllib (Python 3.11+) or fallback to tomli
try:
    import tomllib
except ImportError:
    try:
        import tomli as tomllib  # type: ignore
    except ImportError:
        tomllib = None  # type: ignore

# Placeholder pattern for template substitution
PLACEHOLDER_PATTERN = re.compile(r"\{\{(\w+)\}\}")


@dataclass
class TOMLCommand:
    """
    Represents a custom command defined in TOML.

    Attributes:
        name: Command name (from filename)
        description: Human-readable description
        prompt: Prompt template with {{placeholders}}
        shell: Shell command to execute (optional)
        args: Argument definitions
        extension_name: Parent extension name
        file_path: Path to TOML file
    """

    name: str
    description: str = ""
    prompt: str = ""
    shell: Optional[str] = None
    args: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    extension_name: str = ""
    file_path: Optional[Path] = None

    def substitute(self, values: Dict[str, str]) -> str:
        """
        Substitute placeholders in prompt with provided values.

        Args:
            values: Dict of placeholder names to values

        Returns:
            Substituted prompt string
        """
        result = self.prompt

        def replacer(match: re.Match) -> str:
            key = match.group(1)
            return values.get(key, match.group(0))

        return PLACEHOLDER_PATTERN.sub(replacer, result)

    def execute_shell(self, values: Dict[str, str]) -> Optional[str]:
        """
        Execute the shell command with substituted values.

        Args:
            values: Dict of placeholder names to values

        Returns:
            Command output or None if no shell command
        """
        if not self.shell:
            return None

        # Substitute placeholders in shell command
        command = PLACEHOLDER_PATTERN.sub(lambda m: values.get(m.group(1), m.group(0)), self.shell)

        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=60,
            )
            return result.stdout + result.stderr
        except subprocess.TimeoutExpired:
            logger.error(f"Shell command timed out: {command}")
            return "Error: Command timed out"
        except Exception as e:
            logger.error(f"Shell command failed: {e}")
            return f"Error: {str(e)}"

    def build_prompt(self, args: str = "", values: Optional[Dict[str, str]] = None) -> str:
        """
        Build the final prompt with shell output and substitutions.

        Args:
            args: Raw args string to substitute as {{args}}
            values: Additional values for substitution

        Returns:
            Final prompt string
        """
        all_values = values or {}
        all_values["args"] = args

        # Execute shell command if present
        if self.shell:
            shell_output = self.execute_shell(all_values)
            all_values["shell_output"] = shell_output or ""

        return self.substitute(all_values)


def parse_toml_command(file_path: Path, extension_name: str = "") -> Optional[TOMLCommand]:
    """
    Parse a TOML file into a TOMLCommand.

    Args:
        file_path: Path to .toml file
        extension_name: Name of parent extension

    Returns:
        TOMLCommand or None if parsing fails
    """
    if tomllib is None:
        logger.error("TOML library not available. Install 'tomli' for Python < 3.11")
        return None

    try:
        with open(file_path, "rb") as f:
            data = tomllib.load(f)

        # Get command section
        cmd_data = data.get("command", data)

        # Command name from filename
        name = file_path.stem

        return TOMLCommand(
            name=name,
            description=cmd_data.get("description", ""),
            prompt=cmd_data.get("prompt", ""),
            shell=cmd_data.get("shell"),
            args=cmd_data.get("args", {}),
            extension_name=extension_name,
            file_path=file_path,
        )

    except Exception as e:
        logger.error(f"Failed to parse TOML command {file_path}: {e}")
        return None


def discover_toml_commands(extension_path: Path, extension_name: str = "") -> List[TOMLCommand]:
    """
    Discover all TOML commands in an extension's commands/ directory.

    Args:
        extension_path: Root path of extension
        extension_name: Name of the extension

    Returns:
        List of discovered TOMLCommand objects
    """
    commands_dir = extension_path / "commands"
    if not commands_dir.exists():
        return []

    commands = []
    for toml_file in commands_dir.glob("*.toml"):
        cmd = parse_toml_command(toml_file, extension_name)
        if cmd:
            commands.append(cmd)
            logger.debug(f"Discovered TOML command: {cmd.name} from {extension_name}")

    return commands


def get_prefixed_command_name(command: TOMLCommand) -> str:
    """
    Get the full command name with extension prefix.

    For conflict avoidance, extension commands are prefixed.

    Args:
        command: TOMLCommand instance

    Returns:
        Prefixed command name (e.g., "ext.deploy")
    """
    if command.extension_name:
        return f"{command.extension_name}.{command.name}"
    return command.name


@dataclass
class TOMLCommandRegistry:
    """
    Registry for managing TOML-based commands from extensions.
    """

    _commands: Dict[str, TOMLCommand] = field(default_factory=dict)

    def register(self, command: TOMLCommand, use_prefix: bool = False) -> str:
        """
        Register a TOML command.

        Args:
            command: Command to register
            use_prefix: Whether to use extension prefix

        Returns:
            Registered command name
        """
        if use_prefix or command.name in self._commands:
            name = get_prefixed_command_name(command)
        else:
            name = command.name

        self._commands[name] = command
        logger.debug(f"Registered TOML command: {name}")
        return name

    def get(self, name: str) -> Optional[TOMLCommand]:
        """Get a command by name."""
        return self._commands.get(name)

    def list_commands(self) -> List[str]:
        """Get all registered command names."""
        return list(self._commands.keys())

    def clear(self) -> None:
        """Clear all registered commands."""
        self._commands.clear()


# Global TOML command registry
_toml_registry: Optional[TOMLCommandRegistry] = None


def get_toml_command_registry() -> TOMLCommandRegistry:
    """Get the global TOML command registry."""
    global _toml_registry
    if _toml_registry is None:
        _toml_registry = TOMLCommandRegistry()
    return _toml_registry
