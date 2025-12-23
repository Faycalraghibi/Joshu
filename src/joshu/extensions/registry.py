"""
Extension Registry.

Manages installed and active extensions.
"""

from __future__ import annotations

import logging
from typing import Dict, List, Optional

from joshu.extensions.loader import ExtensionLoader, LoadedExtension

logger = logging.getLogger(__name__)


class ExtensionRegistry:
    """
    Central registry for managing extensions.

    Handles:
    - Extension registration and tracking
    - Enable/disable functionality
    - Extension lookup and listing
    """

    _instance: Optional["ExtensionRegistry"] = None

    def __new__(cls) -> "ExtensionRegistry":
        """Ensure singleton instance."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._extensions = {}
            cls._instance._loader = ExtensionLoader()
        return cls._instance

    def __init__(self):
        """Initialize the registry."""
        if not hasattr(self, "_initialized"):
            self._extensions: Dict[str, LoadedExtension] = {}
            self._loader = ExtensionLoader()
            self._initialized = True

    @property
    def loader(self) -> ExtensionLoader:
        """Get the extension loader."""
        return self._loader

    def register(self, extension: LoadedExtension) -> bool:
        """
        Register a loaded extension.

        Args:
            extension: LoadedExtension to register

        Returns:
            True if successful
        """
        if extension.name in self._extensions:
            logger.warning(f"Extension already registered: {extension.name}")
            return False

        self._extensions[extension.name] = extension
        logger.info(f"Registered extension: {extension.name}")
        return True

    def unregister(self, name: str) -> bool:
        """
        Unregister an extension.

        Args:
            name: Extension name to unregister

        Returns:
            True if successful
        """
        if name not in self._extensions:
            logger.warning(f"Extension not found: {name}")
            return False

        del self._extensions[name]
        logger.info(f"Unregistered extension: {name}")
        return True

    def get_extension(self, name: str) -> Optional[LoadedExtension]:
        """
        Get an extension by name.

        Args:
            name: Extension name

        Returns:
            LoadedExtension or None
        """
        return self._extensions.get(name)

    def list_extensions(self) -> List[LoadedExtension]:
        """
        Get all registered extensions.

        Returns:
            List of loaded extensions
        """
        return list(self._extensions.values())

    def get_active_extensions(self) -> List[LoadedExtension]:
        """
        Get all active extensions.

        Returns:
            List of active extensions
        """
        return [ext for ext in self._extensions.values() if ext.is_active]

    def enable(self, name: str) -> bool:
        """
        Enable an extension.

        Args:
            name: Extension name

        Returns:
            True if successful
        """
        extension = self._extensions.get(name)
        if not extension:
            logger.warning(f"Extension not found: {name}")
            return False

        extension.is_active = True
        logger.info(f"Enabled extension: {name}")
        return True

    def disable(self, name: str) -> bool:
        """
        Disable an extension.

        Args:
            name: Extension name

        Returns:
            True if successful
        """
        extension = self._extensions.get(name)
        if not extension:
            logger.warning(f"Extension not found: {name}")
            return False

        extension.is_active = False
        logger.info(f"Disabled extension: {name}")
        return True

    def discover_and_load(self) -> int:
        """
        Discover and load all extensions.

        Returns:
            Number of extensions loaded
        """
        manifests = self._loader.discover_extensions()
        loaded_count = 0

        for manifest in manifests:
            if not manifest.enabled:
                continue

            extension = self._loader.load_extension(manifest)
            if extension:
                self.register(extension)
                loaded_count += 1

        return loaded_count

    def get_all_context(self) -> str:
        """
        Get combined context content from all active extensions.

        Returns:
            Combined context string
        """
        context_parts = []
        for extension in self.get_active_extensions():
            if extension.context_content:
                context_parts.append(extension.context_content)
        return "\n\n".join(context_parts)

    def get_all_tools(self) -> Dict[str, tuple]:
        """
        Get all tools from active extensions.

        Returns:
            Dict mapping tool name to (handler, config) tuple
        """
        tools = {}
        for extension in self.get_active_extensions():
            for tool_name, handler in extension.loaded_tools.items():
                # Find config
                config = next((t for t in extension.manifest.tools if t.name == tool_name), None)
                if config:
                    tools[tool_name] = (handler, config)
        return tools

    def get_all_commands(self) -> Dict[str, tuple]:
        """
        Get all commands from active extensions.

        Returns:
            Dict mapping command name to (handler, config) tuple
        """
        commands = {}
        for extension in self.get_active_extensions():
            for cmd_name, handler in extension.loaded_commands.items():
                config = extension.manifest.commands.get(cmd_name)
                if config:
                    commands[cmd_name] = (handler, config)
        return commands

    def get_status(self) -> Dict[str, dict]:
        """
        Get status of all extensions.

        Returns:
            Dict with extension status information
        """
        status = {}
        for name, ext in self._extensions.items():
            status[name] = {
                "version": ext.version,
                "active": ext.is_active,
                "path": str(ext.path) if ext.path else None,
                "tools": list(ext.loaded_tools.keys()),
                "commands": list(ext.loaded_commands.keys()),
                "has_context": bool(ext.context_content),
            }
        return status

    def clear(self) -> None:
        """Clear all extensions (for testing)."""
        self._extensions.clear()
        logger.info("Cleared all extensions")


# Global registry instance
_registry: Optional[ExtensionRegistry] = None


def get_extension_registry() -> ExtensionRegistry:
    """
    Get the global extension registry instance.

    Returns:
        ExtensionRegistry singleton
    """
    global _registry
    if _registry is None:
        _registry = ExtensionRegistry()
    return _registry
