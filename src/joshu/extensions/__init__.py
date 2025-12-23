"""
Joshu Extensions Framework.

This package provides the extension system for Joshu CLI, enabling:
- Custom tool registration via extensions
- MCP server configurations
- Custom commands
- Context files and prompts
"""

from joshu.extensions.loader import ExtensionLoader, LoadedExtension
from joshu.extensions.manifest import ExtensionManifest, load_manifest
from joshu.extensions.registry import ExtensionRegistry, get_extension_registry

__all__ = [
    "ExtensionManifest",
    "load_manifest",
    "ExtensionLoader",
    "LoadedExtension",
    "ExtensionRegistry",
    "get_extension_registry",
]
