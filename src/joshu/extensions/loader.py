"""
Extension Loader.

Discovers, loads, and activates extensions.
"""

from __future__ import annotations

import importlib.util
import logging
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, List, Optional

from joshu.extensions.manifest import (
    ExtensionManifest,
    load_manifest,
)

logger = logging.getLogger(__name__)

# Default extension directories
DEFAULT_EXTENSION_DIRS = [
    Path.home() / ".joshu" / "extensions",
    Path.cwd() / ".joshu" / "extensions",
]


@dataclass
class LoadedExtension:
    """Represents a loaded and active extension."""

    manifest: ExtensionManifest
    loaded_tools: Dict[str, Callable] = field(default_factory=dict)
    loaded_commands: Dict[str, Callable] = field(default_factory=dict)
    context_content: str = ""
    is_active: bool = False

    @property
    def name(self) -> str:
        return self.manifest.name

    @property
    def version(self) -> str:
        return self.manifest.version

    @property
    def path(self) -> Optional[Path]:
        return self.manifest.extension_path


class ExtensionLoader:
    """
    Discovers and loads extensions.

    Handles:
    - Extension discovery in configured paths
    - Manifest loading and validation
    - Tool/command handler loading
    - Context file loading
    """

    def __init__(self, search_paths: Optional[List[Path]] = None):
        """
        Initialize the extension loader.

        Args:
            search_paths: Paths to search for extensions
        """
        self.search_paths = search_paths or DEFAULT_EXTENSION_DIRS.copy()

    def add_search_path(self, path: Path) -> None:
        """Add a search path for extensions."""
        if path not in self.search_paths:
            self.search_paths.append(path)

    def discover_extensions(self) -> List[ExtensionManifest]:
        """
        Discover all extensions in search paths.

        Returns:
            List of discovered extension manifests
        """
        manifests = []

        for search_path in self.search_paths:
            if not search_path.exists():
                continue

            logger.debug(f"Searching for extensions in: {search_path}")

            # Check subdirectories for extensions
            for item in search_path.iterdir():
                if item.is_dir():
                    manifest = load_manifest(item)
                    if manifest:
                        manifests.append(manifest)

        logger.info(f"Discovered {len(manifests)} extensions")
        return manifests

    def load_extension(self, manifest: ExtensionManifest) -> Optional[LoadedExtension]:
        """
        Load and activate an extension.

        Args:
            manifest: Extension manifest to load

        Returns:
            LoadedExtension if successful, None otherwise
        """
        try:
            extension_path = manifest.extension_path
            if not extension_path:
                logger.error(f"Extension {manifest.name} has no path set")
                return None

            loaded = LoadedExtension(manifest=manifest)

            # Load context files
            context_parts = []
            for context_file in manifest.context_files:
                file_path = extension_path / context_file
                if file_path.exists():
                    try:
                        content = file_path.read_text(encoding="utf-8")
                        context_parts.append(f"# From {manifest.name}: {context_file}\n{content}")
                    except Exception as e:
                        logger.warning(f"Failed to load context file {context_file}: {e}")
            loaded.context_content = "\n\n".join(context_parts)

            # Load tool handlers
            for tool_config in manifest.tools:
                handler_path = extension_path / tool_config.handler
                handler = self._load_handler(handler_path, tool_config.name)
                if handler:
                    loaded.loaded_tools[tool_config.name] = handler

            # Load command handlers
            for cmd_name, cmd_config in manifest.commands.items():
                handler_path = extension_path / cmd_config.handler
                handler = self._load_handler(handler_path, cmd_name)
                if handler:
                    loaded.loaded_commands[cmd_name] = handler

            loaded.is_active = True
            logger.info(f"Loaded extension: {manifest.name} v{manifest.version}")
            return loaded

        except Exception as e:
            logger.error(f"Failed to load extension {manifest.name}: {e}")
            return None

    def _load_handler(self, handler_path: Path, name: str) -> Optional[Callable]:
        """
        Load a handler function from a Python file.

        Args:
            handler_path: Path to handler script
            name: Name of the function to load

        Returns:
            Callable handler or None
        """
        if not handler_path.exists():
            logger.warning(f"Handler not found: {handler_path}")
            return None

        try:
            spec = importlib.util.spec_from_file_location(name, handler_path)
            if spec and spec.loader:
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)

                # Look for a function with the expected name
                handler = getattr(module, name, None)
                if handler and callable(handler):
                    return handler

                # Fallback: look for 'main' or 'handler'
                for fallback in ["main", "handler", "run"]:
                    handler = getattr(module, fallback, None)
                    if handler and callable(handler):
                        return handler

                logger.warning(f"No callable handler found in {handler_path}")
            return None

        except Exception as e:
            logger.error(f"Failed to load handler {handler_path}: {e}")
            return None

    def install_from_git(
        self,
        repo_url: str,
        target_dir: Optional[Path] = None,
    ) -> Optional[ExtensionManifest]:
        """
        Install an extension from a Git repository.

        Args:
            repo_url: Git repository URL
            target_dir: Target directory for installation

        Returns:
            Installed extension manifest or None
        """
        target_dir = target_dir or DEFAULT_EXTENSION_DIRS[0]
        target_dir.mkdir(parents=True, exist_ok=True)

        # Extract repo name for directory
        repo_name = repo_url.rstrip("/").split("/")[-1]
        if repo_name.endswith(".git"):
            repo_name = repo_name[:-4]

        install_path = target_dir / repo_name

        try:
            if install_path.exists():
                logger.info(f"Updating extension: {repo_name}")
                subprocess.run(
                    ["git", "pull"],
                    cwd=install_path,
                    check=True,
                    capture_output=True,
                )
            else:
                logger.info(f"Installing extension from: {repo_url}")
                subprocess.run(
                    ["git", "clone", repo_url, str(install_path)],
                    check=True,
                    capture_output=True,
                )

            manifest = load_manifest(install_path)
            if manifest:
                logger.info(f"Installed extension: {manifest.name} v{manifest.version}")
                return manifest
            else:
                logger.error(f"No valid manifest found in {repo_url}")
                return None

        except subprocess.CalledProcessError as e:
            logger.error(f"Git operation failed: {e}")
            return None
        except Exception as e:
            logger.error(f"Failed to install extension: {e}")
            return None

    def uninstall_extension(self, name: str) -> bool:
        """
        Uninstall an extension by name.

        Args:
            name: Extension name to uninstall

        Returns:
            True if successful
        """
        for search_path in self.search_paths:
            extension_path = search_path / name
            if extension_path.exists():
                try:
                    import shutil

                    shutil.rmtree(extension_path)
                    logger.info(f"Uninstalled extension: {name}")
                    return True
                except Exception as e:
                    logger.error(f"Failed to uninstall {name}: {e}")
                    return False

        logger.warning(f"Extension not found: {name}")
        return False
