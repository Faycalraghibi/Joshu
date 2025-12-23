"""
Extension Manifest Schema and Parsing.

Defines the joshu-extension.json manifest format and validation.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Manifest filename
MANIFEST_FILENAME = "joshu-extension.json"


@dataclass
class MCPServerConfig:
    """Configuration for an MCP server in an extension."""

    command: str
    args: List[str] = field(default_factory=list)
    env: Dict[str, str] = field(default_factory=dict)
    transport: str = "stdio"  # stdio, http, sse

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MCPServerConfig":
        return cls(
            command=data.get("command", ""),
            args=data.get("args", []),
            env=data.get("env", {}),
            transport=data.get("transport", "stdio"),
        )


@dataclass
class CommandConfig:
    """Configuration for a custom command in an extension."""

    description: str
    handler: str  # Path to handler script
    args: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CommandConfig":
        return cls(
            description=data.get("description", ""),
            handler=data.get("handler", ""),
            args=data.get("args", {}),
        )


@dataclass
class ToolConfig:
    """Configuration for a custom tool in an extension."""

    name: str
    description: str
    handler: str  # Path to handler script or module
    parameters: Dict[str, Any] = field(default_factory=dict)
    requires_approval: bool = False

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ToolConfig":
        return cls(
            name=data.get("name", ""),
            description=data.get("description", ""),
            handler=data.get("handler", ""),
            parameters=data.get("parameters", {}),
            requires_approval=data.get("requires_approval", False),
        )


@dataclass
class ExtensionManifest:
    """
    Extension manifest definition.

    Represents the contents of a joshu-extension.json file.
    """

    name: str
    version: str
    description: str = ""
    author: Optional[str] = None
    license: Optional[str] = None
    homepage: Optional[str] = None
    repository: Optional[str] = None

    # Extension components
    context_files: List[str] = field(default_factory=list)
    mcp_servers: Dict[str, MCPServerConfig] = field(default_factory=dict)
    commands: Dict[str, CommandConfig] = field(default_factory=dict)
    tools: List[ToolConfig] = field(default_factory=list)

    # Extension settings
    enabled: bool = True
    auto_activate: bool = True

    # Path to the extension directory (set when loaded)
    extension_path: Optional[Path] = None

    def validate(self) -> List[str]:
        """
        Validate the manifest.

        Returns:
            List of validation error messages (empty if valid)
        """
        errors = []

        if not self.name:
            errors.append("Extension name is required")
        elif not self.name.replace("-", "").replace("_", "").isalnum():
            errors.append("Extension name must be alphanumeric (with - and _)")

        if not self.version:
            errors.append("Extension version is required")

        for tool in self.tools:
            if not tool.name:
                errors.append("Tool name is required")
            if not tool.handler:
                errors.append(f"Tool '{tool.name}' requires a handler")

        for name, server in self.mcp_servers.items():
            if not server.command:
                errors.append(f"MCP server '{name}' requires a command")

        return errors

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "author": self.author,
            "license": self.license,
            "homepage": self.homepage,
            "repository": self.repository,
            "contextFiles": self.context_files,
            "mcpServers": {
                name: {
                    "command": cfg.command,
                    "args": cfg.args,
                    "env": cfg.env,
                    "transport": cfg.transport,
                }
                for name, cfg in self.mcp_servers.items()
            },
            "commands": {
                name: {
                    "description": cfg.description,
                    "handler": cfg.handler,
                    "args": cfg.args,
                }
                for name, cfg in self.commands.items()
            },
            "tools": [
                {
                    "name": t.name,
                    "description": t.description,
                    "handler": t.handler,
                    "parameters": t.parameters,
                    "requires_approval": t.requires_approval,
                }
                for t in self.tools
            ],
            "enabled": self.enabled,
            "autoActivate": self.auto_activate,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ExtensionManifest":
        """Create manifest from dictionary."""
        mcp_servers = {
            name: MCPServerConfig.from_dict(cfg) for name, cfg in data.get("mcpServers", {}).items()
        }

        commands = {
            name: CommandConfig.from_dict(cfg) for name, cfg in data.get("commands", {}).items()
        }

        tools = [ToolConfig.from_dict(tool) for tool in data.get("tools", [])]

        return cls(
            name=data.get("name", ""),
            version=data.get("version", ""),
            description=data.get("description", ""),
            author=data.get("author"),
            license=data.get("license"),
            homepage=data.get("homepage"),
            repository=data.get("repository"),
            context_files=data.get("contextFiles", []),
            mcp_servers=mcp_servers,
            commands=commands,
            tools=tools,
            enabled=data.get("enabled", True),
            auto_activate=data.get("autoActivate", True),
        )


def load_manifest(path: Path) -> Optional[ExtensionManifest]:
    """
    Load an extension manifest from a directory or file.

    Args:
        path: Path to extension directory or manifest file

    Returns:
        ExtensionManifest or None if loading fails
    """
    try:
        if path.is_dir():
            manifest_path = path / MANIFEST_FILENAME
        else:
            manifest_path = path

        if not manifest_path.exists():
            logger.warning(f"Manifest not found: {manifest_path}")
            return None

        with open(manifest_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        manifest = ExtensionManifest.from_dict(data)
        manifest.extension_path = manifest_path.parent if manifest_path.is_file() else path

        # Validate
        errors = manifest.validate()
        if errors:
            for error in errors:
                logger.error(f"Manifest validation error: {error}")
            return None

        logger.info(f"Loaded extension manifest: {manifest.name} v{manifest.version}")
        return manifest

    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in manifest: {e}")
        return None
    except Exception as e:
        logger.error(f"Failed to load manifest: {e}")
        return None


def save_manifest(manifest: ExtensionManifest, path: Path) -> bool:
    """
    Save an extension manifest to a file.

    Args:
        manifest: Manifest to save
        path: Path to save to

    Returns:
        True if successful
    """
    try:
        if path.is_dir():
            path = path / MANIFEST_FILENAME

        path.parent.mkdir(parents=True, exist_ok=True)

        with open(path, "w", encoding="utf-8") as f:
            json.dump(manifest.to_dict(), f, indent=2)

        logger.info(f"Saved extension manifest: {path}")
        return True

    except Exception as e:
        logger.error(f"Failed to save manifest: {e}")
        return False
