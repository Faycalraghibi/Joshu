"""
A2A Command Registry for central command management.

Provides registration, retrieval, and discovery of commands.

NOTE: This module provides transport and orchestration only.
It must not introduce new agent logic or execution semantics.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from joshu.a2a.commands.types import Command

logger = logging.getLogger(__name__)


class CommandRegistry:
    """
    Central registry for A2A commands.

    Manages registration and retrieval of commands, supporting
    both top-level commands and nested subcommands.

    Example:
        >>> registry = CommandRegistry()
        >>> registry.register(InitCommand())
        >>> cmd = registry.get("init")
        >>> if cmd:
        ...     async for result in cmd.execute(ctx, args):
        ...         print(result)
    """

    def __init__(self) -> None:
        self._commands: Dict[str, Command] = {}

    def register(self, command: Command) -> None:
        """
        Register a command.

        Args:
            command: Command to register

        Raises:
            ValueError: If command with same name already exists
        """
        if command.name in self._commands:
            raise ValueError(f"Command '{command.name}' already registered")

        self._commands[command.name] = command
        logger.debug(f"Registered command: {command.name}")

        # Log subcommands if any
        for sub in command.subcommands:
            logger.debug(f"  Subcommand: {command.name} {sub.name}")

    def unregister(self, name: str) -> bool:
        """
        Unregister a command.

        Args:
            name: Command name to unregister

        Returns:
            True if unregistered, False if not found
        """
        if name in self._commands:
            del self._commands[name]
            logger.debug(f"Unregistered command: {name}")
            return True
        return False

    def get(self, name: str) -> Optional[Command]:
        """
        Get a command by name.

        Supports dotted notation for subcommands (e.g., "extensions.list").

        Args:
            name: Command name or "parent.child" for subcommands

        Returns:
            Command if found, None otherwise
        """
        parts = name.split(".", 1)
        cmd = self._commands.get(parts[0])

        if cmd is None:
            return None

        # Handle subcommand lookup
        if len(parts) > 1:
            for sub in cmd.subcommands:
                if sub.name == parts[1]:
                    return sub
            return None

        return cmd

    def get_all(self) -> List[Command]:
        """Get all registered top-level commands."""
        return list(self._commands.values())

    def list_commands(self) -> List[Dict[str, Any]]:
        """
        List all commands for API response.

        Returns:
            List of command dictionaries with name, description,
            arguments, and subcommands.
        """
        result = []
        for cmd in self._commands.values():
            cmd_dict = {
                "name": cmd.name,
                "description": cmd.description,
                "arguments": [arg.to_dict() for arg in cmd.arguments],
                "subcommands": [],
            }

            for sub in cmd.subcommands:
                cmd_dict["subcommands"].append(
                    {
                        "name": sub.name,
                        "description": sub.description,
                        "arguments": [arg.to_dict() for arg in sub.arguments],
                    }
                )

            result.append(cmd_dict)

        return result

    def has(self, name: str) -> bool:
        """Check if a command is registered."""
        return self.get(name) is not None

    def clear(self) -> None:
        """Clear all registered commands (for testing)."""
        self._commands.clear()


# Module-level registry singleton
_registry: Optional[CommandRegistry] = None


def get_command_registry() -> CommandRegistry:
    """Get the global command registry instance."""
    global _registry
    if _registry is None:
        _registry = CommandRegistry()
    return _registry


def register_default_commands() -> None:
    """
    Register default built-in commands.

    Call this during server startup to register standard commands.
    """
    from joshu.a2a.commands.init_command import InitCommand
    from joshu.a2a.commands.restore import RestoreCommand

    registry = get_command_registry()

    # Only register if not already registered
    if not registry.has("init"):
        registry.register(InitCommand())

    if not registry.has("restore"):
        registry.register(RestoreCommand())

    logger.info(f"Registered {len(registry.get_all())} default commands")
