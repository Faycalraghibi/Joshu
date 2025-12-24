"""
Joshu Extensions Framework.

This package provides the extension system for Joshu CLI, enabling:
- Custom tool registration via extensions
- MCP server configurations
- Custom commands (JSON and TOML-based)
- Context files and prompts
- Extension settings management
"""

from joshu.extensions.commands import (
    TOMLCommand,
    TOMLCommandRegistry,
    discover_toml_commands,
    get_toml_command_registry,
)
from joshu.extensions.loader import ExtensionLoader, LoadedExtension
from joshu.extensions.manifest import ExtensionManifest, load_manifest
from joshu.extensions.registry import ExtensionRegistry, get_extension_registry
from joshu.extensions.settings import (
    ExtensionSettings,
    SettingDefinition,
    load_extension_settings,
)

__all__ = [
    # Manifest
    "ExtensionManifest",
    "load_manifest",
    # Loader
    "ExtensionLoader",
    "LoadedExtension",
    # Registry
    "ExtensionRegistry",
    "get_extension_registry",
    # Commands
    "TOMLCommand",
    "TOMLCommandRegistry",
    "discover_toml_commands",
    "get_toml_command_registry",
    # Settings
    "ExtensionSettings",
    "SettingDefinition",
    "load_extension_settings",
]
