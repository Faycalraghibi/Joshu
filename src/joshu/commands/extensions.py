"""
Extension Management Command Handlers.

Provides CLI command handlers for managing Joshu extensions:
- joshu extension install - Install from Git or GitHub Release
- joshu extension uninstall - Remove extension
- joshu extension enable/disable - Activation control
- joshu extension update - Update extensions
- joshu extension link - Symlink for local development
- joshu extension new - Bootstrap from template
- joshu extension list - List extensions with status
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Optional

from joshu.commands.types import (
    CommandActionReturn,
    ErrorActionReturn,
    MessageActionReturn,
)
from joshu.extensions.loader import ExtensionLoader
from joshu.extensions.manifest import ExtensionManifest, save_manifest
from joshu.extensions.registry import get_extension_registry

logger = logging.getLogger(__name__)


# Extension scope types
ScopeType = Literal["user", "workspace"]


@dataclass
class ExtensionInstallConfig:
    """Configuration for extension installation."""

    source: str  # Git URL or GitHub repo
    ref: Optional[str] = None  # Branch, tag, or commit
    pre_release: bool = False
    scope: ScopeType = "user"


def extension_install(config: ExtensionInstallConfig) -> CommandActionReturn:
    """
    Install an extension from Git repository or GitHub Release.

    Args:
        config: Installation configuration

    Returns:
        CommandActionReturn with result
    """
    try:
        loader = ExtensionLoader()

        # Determine target directory based on scope
        if config.scope == "workspace":
            target_dir = Path.cwd() / ".joshu" / "extensions"
        else:
            target_dir = Path.home() / ".joshu" / "extensions"

        target_dir.mkdir(parents=True, exist_ok=True)

        # Install from git
        manifest = loader.install_from_git(config.source, target_dir)

        if manifest:
            # Register with the extension registry
            registry = get_extension_registry()
            extension = loader.load_extension(manifest)
            if extension:
                registry.register(extension)

            logger.info(f"Installed extension: {manifest.name} v{manifest.version}")

            return MessageActionReturn(
                message=f"✓ Installed extension '{manifest.name}' v{manifest.version}",
                message_type="success",
                metadata={
                    "name": manifest.name,
                    "version": manifest.version,
                    "path": str(manifest.extension_path),
                },
            )
        else:
            return ErrorActionReturn(
                error_message=f"Failed to install from: {config.source}",
                error_code="INSTALL_FAILED",
                recoverable=True,
            )

    except Exception as e:
        logger.error(f"Extension installation failed: {e}")
        return ErrorActionReturn(
            error_message=f"Installation failed: {str(e)}",
            error_code="INSTALL_FAILED",
            recoverable=True,
        )


def extension_uninstall(name: str) -> CommandActionReturn:
    """
    Uninstall an extension.

    Args:
        name: Extension name to uninstall

    Returns:
        CommandActionReturn with result
    """
    try:
        registry = get_extension_registry()
        loader = registry.loader

        # Check if extension exists
        extension = registry.get_extension(name)
        if not extension:
            return ErrorActionReturn(
                error_message=f"Extension not found: {name}",
                error_code="NOT_FOUND",
                recoverable=True,
            )

        # Unregister from registry
        registry.unregister(name)

        # Remove files
        if loader.uninstall_extension(name):
            logger.info(f"Uninstalled extension: {name}")
            return MessageActionReturn(
                message=f"✓ Uninstalled extension '{name}'",
                message_type="success",
            )
        else:
            return ErrorActionReturn(
                error_message=f"Failed to remove extension files: {name}",
                error_code="UNINSTALL_FAILED",
                recoverable=True,
            )

    except Exception as e:
        logger.error(f"Extension uninstall failed: {e}")
        return ErrorActionReturn(
            error_message=f"Uninstall failed: {str(e)}",
            error_code="UNINSTALL_FAILED",
            recoverable=True,
        )


def extension_enable(name: str, scope: ScopeType = "user") -> CommandActionReturn:
    """
    Enable an extension.

    Args:
        name: Extension name
        scope: user or workspace scope

    Returns:
        CommandActionReturn with result
    """
    try:
        registry = get_extension_registry()

        if registry.enable(name):
            return MessageActionReturn(
                message=f"✓ Enabled extension '{name}' (scope: {scope})",
                message_type="success",
            )
        else:
            return ErrorActionReturn(
                error_message=f"Extension not found: {name}",
                error_code="NOT_FOUND",
                recoverable=True,
            )

    except Exception as e:
        logger.error(f"Failed to enable extension: {e}")
        return ErrorActionReturn(
            error_message=f"Enable failed: {str(e)}",
            error_code="ENABLE_FAILED",
            recoverable=True,
        )


def extension_disable(name: str, scope: ScopeType = "user") -> CommandActionReturn:
    """
    Disable an extension.

    Args:
        name: Extension name
        scope: user or workspace scope

    Returns:
        CommandActionReturn with result
    """
    try:
        registry = get_extension_registry()

        if registry.disable(name):
            return MessageActionReturn(
                message=f"✓ Disabled extension '{name}' (scope: {scope})",
                message_type="success",
            )
        else:
            return ErrorActionReturn(
                error_message=f"Extension not found: {name}",
                error_code="NOT_FOUND",
                recoverable=True,
            )

    except Exception as e:
        logger.error(f"Failed to disable extension: {e}")
        return ErrorActionReturn(
            error_message=f"Disable failed: {str(e)}",
            error_code="DISABLE_FAILED",
            recoverable=True,
        )


def extension_update(
    name: Optional[str] = None, all_extensions: bool = False
) -> CommandActionReturn:
    """
    Update extension(s).

    Args:
        name: Extension name to update (None if updating all)
        all_extensions: Update all installed extensions

    Returns:
        CommandActionReturn with result
    """
    try:
        registry = get_extension_registry()
        updated = []

        if all_extensions:
            extensions = registry.list_extensions()
        elif name:
            ext = registry.get_extension(name)
            extensions = [ext] if ext else []
        else:
            return ErrorActionReturn(
                error_message="Specify extension name or use --all",
                error_code="INVALID_ARGS",
                recoverable=True,
            )

        for ext in extensions:
            if ext.path and ext.path.exists():
                # Try git pull in extension directory
                try:
                    import subprocess

                    result = subprocess.run(
                        ["git", "pull"],
                        cwd=ext.path,
                        capture_output=True,
                        text=True,
                    )
                    if result.returncode == 0:
                        updated.append(ext.name)
                        logger.info(f"Updated extension: {ext.name}")
                except Exception as e:
                    logger.warning(f"Failed to update {ext.name}: {e}")

        if updated:
            return MessageActionReturn(
                message=f"✓ Updated {len(updated)} extension(s): {', '.join(updated)}",
                message_type="success",
                metadata={"updated": updated},
            )
        else:
            return MessageActionReturn(
                message="No extensions were updated",
                message_type="info",
            )

    except Exception as e:
        logger.error(f"Extension update failed: {e}")
        return ErrorActionReturn(
            error_message=f"Update failed: {str(e)}",
            error_code="UPDATE_FAILED",
            recoverable=True,
        )


def extension_link(path: str = ".") -> CommandActionReturn:
    """
    Link a local directory as an extension for development.

    Args:
        path: Path to extension directory (default: current)

    Returns:
        CommandActionReturn with result
    """
    try:
        source_path = Path(path).resolve()

        # Verify it's a valid extension
        manifest_file = source_path / "joshu-extension.json"
        if not manifest_file.exists():
            return ErrorActionReturn(
                error_message=f"No joshu-extension.json found in {source_path}",
                error_code="INVALID_EXTENSION",
                recoverable=True,
            )

        # Load manifest to get name
        from joshu.extensions.manifest import load_manifest

        manifest = load_manifest(source_path)
        if not manifest:
            return ErrorActionReturn(
                error_message="Failed to parse extension manifest",
                error_code="INVALID_MANIFEST",
                recoverable=True,
            )

        # Create symlink in user extensions directory
        target_dir = Path.home() / ".joshu" / "extensions"
        target_dir.mkdir(parents=True, exist_ok=True)

        link_path = target_dir / manifest.name

        # Remove existing link if present
        if link_path.exists() or link_path.is_symlink():
            if link_path.is_symlink():
                link_path.unlink()
            else:
                return ErrorActionReturn(
                    error_message=f"Extension '{manifest.name}' already exists and is not a symlink",
                    error_code="EXISTS",
                    recoverable=True,
                )

        # Create symlink
        link_path.symlink_to(source_path, target_is_directory=True)

        logger.info(f"Linked extension: {manifest.name} -> {source_path}")

        return MessageActionReturn(
            message=f"✓ Linked extension '{manifest.name}' from {source_path}",
            message_type="success",
            metadata={
                "name": manifest.name,
                "source": str(source_path),
                "link": str(link_path),
            },
        )

    except Exception as e:
        logger.error(f"Extension link failed: {e}")
        return ErrorActionReturn(
            error_message=f"Link failed: {str(e)}",
            error_code="LINK_FAILED",
            recoverable=True,
        )


def extension_new(
    name: str,
    template: str = "basic",
    output_dir: Optional[str] = None,
) -> CommandActionReturn:
    """
    Create a new extension from template.

    Args:
        name: Extension name
        template: Template type (basic, mcp-server)
        output_dir: Output directory (default: current)

    Returns:
        CommandActionReturn with result
    """
    try:
        output_path = Path(output_dir) if output_dir else Path.cwd()
        extension_path = output_path / name

        if extension_path.exists():
            return ErrorActionReturn(
                error_message=f"Directory already exists: {extension_path}",
                error_code="EXISTS",
                recoverable=True,
            )

        # Create extension directory
        extension_path.mkdir(parents=True)

        # Create manifest
        manifest = ExtensionManifest(
            name=name,
            version="0.1.0",
            description=f"{name} extension for Joshu",
        )

        if template == "mcp-server":
            # Add MCP server configuration
            from joshu.extensions.manifest import MCPServerConfig

            manifest.mcp_servers["main"] = MCPServerConfig(
                command="node",
                args=["dist/index.js"],
            )

        # Save manifest
        save_manifest(manifest, extension_path / "joshu-extension.json")

        # Create context file
        context_file = extension_path / "JOSHU.md"
        context_file.write_text(f"# {name}\n\nThis is the context file for the {name} extension.\n")

        # Create commands directory
        commands_dir = extension_path / "commands"
        commands_dir.mkdir()

        logger.info(f"Created extension: {name} at {extension_path}")

        return MessageActionReturn(
            message=f"✓ Created extension '{name}' at {extension_path}",
            message_type="success",
            metadata={
                "name": name,
                "path": str(extension_path),
                "template": template,
            },
        )

    except Exception as e:
        logger.error(f"Extension creation failed: {e}")
        return ErrorActionReturn(
            error_message=f"Creation failed: {str(e)}",
            error_code="CREATE_FAILED",
            recoverable=True,
        )


def extension_list() -> CommandActionReturn:
    """
    List all installed extensions with status.

    Returns:
        CommandActionReturn with extension list
    """
    try:
        registry = get_extension_registry()

        # Discover and load if needed
        if not registry.list_extensions():
            registry.discover_and_load()

        extensions = registry.list_extensions()

        if not extensions:
            return MessageActionReturn(
                message="No extensions installed",
                message_type="info",
            )

        lines = ["**Installed Extensions:**", ""]

        for ext in extensions:
            status_icon = "🟢" if ext.is_active else "⚪"
            status_text = "enabled" if ext.is_active else "disabled"

            lines.append(f"  {status_icon} **{ext.name}** v{ext.version} ({status_text})")

            if ext.path:
                # Check if it's a symlink (development mode)
                if ext.path.is_symlink():
                    lines.append(f"      📎 Linked: {ext.path.resolve()}")
                else:
                    lines.append(f"      📁 {ext.path}")

            if ext.loaded_tools:
                lines.append(f"      🔧 Tools: {', '.join(ext.loaded_tools.keys())}")

            if ext.loaded_commands:
                lines.append(f"      ⚡ Commands: {', '.join(ext.loaded_commands.keys())}")

        return MessageActionReturn(
            message="\n".join(lines),
            message_type="info",
            metadata={"extensions": registry.get_status()},
        )

    except Exception as e:
        logger.error(f"Failed to list extensions: {e}")
        return ErrorActionReturn(
            error_message=f"List failed: {str(e)}",
            error_code="LIST_FAILED",
            recoverable=True,
        )
