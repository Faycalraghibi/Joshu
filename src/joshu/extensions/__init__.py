"""
TOML custom commands (see joshu.core.custom_commands).

Custom slash commands can be written as Markdown or as TOML; this package
parses the TOML form and its {{args}} / !{shell} placeholders.
"""

from joshu.extensions.commands import (
    TOMLCommand,
    TOMLCommandRegistry,
    discover_toml_commands,
    get_toml_command_registry,
)

__all__ = [
    "TOMLCommand",
    "TOMLCommandRegistry",
    "discover_toml_commands",
    "get_toml_command_registry",
]
