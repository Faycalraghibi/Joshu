"""
Extension Settings Management.

Handles extension-specific settings with support for:
- .env file storage within extension directory
- Sensitive values stored in system keychain
- Settings listing and modification
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

try:
    import keyring

    KEYRING_AVAILABLE = True
except ImportError:
    KEYRING_AVAILABLE = False
    keyring = None  # type: ignore

SETTINGS_FILENAME = ".env"

KEYRING_SERVICE_PREFIX = "joshu-extension"


@dataclass
class SettingDefinition:
    """
    Definition of an extension setting.

    Attributes:
        name: Setting name
        description: Human-readable description
        default: Default value
        sensitive: Whether to store in keychain
        required: Whether setting is required
    """

    name: str
    description: str = ""
    default: Optional[str] = None
    sensitive: bool = False
    required: bool = False


@dataclass
class ExtensionSettings:
    """
    Manages settings for a single extension.

    Attributes:
        extension_name: Name of the extension
        extension_path: Path to extension directory
        definitions: Setting definitions
        values: Current setting values
    """

    extension_name: str
    extension_path: Path
    definitions: Dict[str, SettingDefinition] = field(default_factory=dict)
    values: Dict[str, str] = field(default_factory=dict)

    def load(self) -> None:
        """Load settings from .env file and keychain."""
        env_file = self.extension_path / SETTINGS_FILENAME
        if env_file.exists():
            self._load_env_file(env_file)

        if KEYRING_AVAILABLE:
            for name, definition in self.definitions.items():
                if definition.sensitive and name not in self.values:
                    try:
                        value = keyring.get_password(
                            f"{KEYRING_SERVICE_PREFIX}.{self.extension_name}", name
                        )
                        if value:
                            self.values[name] = value
                    except Exception as e:
                        logger.warning(f"Failed to load keychain value {name}: {e}")

        for name, definition in self.definitions.items():
            if name not in self.values and definition.default is not None:
                self.values[name] = definition.default

    def save(self) -> None:
        """Save settings to .env file and keychain."""
        env_values = {}
        keychain_values = {}

        for name, value in self.values.items():
            definition = self.definitions.get(name)
            if definition and definition.sensitive:
                keychain_values[name] = value
            else:
                env_values[name] = value

        if env_values:
            self._save_env_file(self.extension_path / SETTINGS_FILENAME, env_values)

        if keychain_values and KEYRING_AVAILABLE:
            for name, value in keychain_values.items():
                try:
                    keyring.set_password(
                        f"{KEYRING_SERVICE_PREFIX}.{self.extension_name}", name, value
                    )
                except Exception as e:
                    logger.error(f"Failed to save to keychain {name}: {e}")

    def get(self, name: str) -> Optional[str]:
        """Get a setting value."""
        return self.values.get(name)

    def set(self, name: str, value: str) -> None:
        """Set a setting value."""
        self.values[name] = value

    def delete(self, name: str) -> bool:
        """Delete a setting value."""
        if name in self.values:
            del self.values[name]

            definition = self.definitions.get(name)
            if definition and definition.sensitive and KEYRING_AVAILABLE:
                try:
                    keyring.delete_password(f"{KEYRING_SERVICE_PREFIX}.{self.extension_name}", name)
                except Exception:
                    pass

            return True
        return False

    def list_settings(self) -> List[Dict[str, Any]]:
        """
        List all settings with their status.

        Returns:
            List of setting info dicts
        """
        result = []
        for name, definition in self.definitions.items():
            value = self.values.get(name)
            result.append(
                {
                    "name": name,
                    "description": definition.description,
                    "value": "***" if definition.sensitive and value else value,
                    "sensitive": definition.sensitive,
                    "required": definition.required,
                    "has_value": value is not None,
                }
            )
        return result

    def _load_env_file(self, path: Path) -> None:
        """Load values from .env file."""
        try:
            with open(path) as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        key, _, value = line.partition("=")
                        key = key.strip()
                        value = value.strip().strip("\"'")
                        self.values[key] = value
        except Exception as e:
            logger.error(f"Failed to load .env file: {e}")

    def _save_env_file(self, path: Path, values: Dict[str, str]) -> None:
        """Save values to .env file."""
        try:
            lines = []
            for key, value in values.items():
                # Quote value if it contains spaces
                if " " in value:
                    value = f'"{value}"'
                lines.append(f"{key}={value}")

            path.write_text("\n".join(lines) + "\n")
        except Exception as e:
            logger.error(f"Failed to save .env file: {e}")


def load_extension_settings(
    extension_name: str,
    extension_path: Path,
    definitions: Optional[Dict[str, SettingDefinition]] = None,
) -> ExtensionSettings:
    """
    Load settings for an extension.

    Args:
        extension_name: Name of the extension
        extension_path: Path to extension directory
        definitions: Optional setting definitions

    Returns:
        ExtensionSettings instance
    """
    settings = ExtensionSettings(
        extension_name=extension_name,
        extension_path=extension_path,
        definitions=definitions or {},
    )
    settings.load()
    return settings


# Command handlers for settings management


def extension_settings_list(extension_name: str) -> Dict[str, Any]:
    """
    List settings for an extension.

    Args:
        extension_name: Extension name

    Returns:
        Dict with settings info
    """
    from joshu.extensions.registry import get_extension_registry

    registry = get_extension_registry()
    extension = registry.get_extension(extension_name)

    if not extension:
        return {"error": f"Extension not found: {extension_name}"}

    if not extension.path:
        return {"error": f"Extension has no path: {extension_name}"}

    settings = load_extension_settings(extension_name, extension.path)
    return {
        "extension": extension_name,
        "settings": settings.list_settings(),
        "keychain_available": KEYRING_AVAILABLE,
    }


def extension_settings_set(extension_name: str, key: str, value: str) -> Dict[str, Any]:
    """
    Set a setting for an extension.

    Args:
        extension_name: Extension name
        key: Setting key
        value: Setting value

    Returns:
        Result dict
    """
    from joshu.extensions.registry import get_extension_registry

    registry = get_extension_registry()
    extension = registry.get_extension(extension_name)

    if not extension:
        return {"error": f"Extension not found: {extension_name}"}

    if not extension.path:
        return {"error": f"Extension has no path: {extension_name}"}

    settings = load_extension_settings(extension_name, extension.path)
    settings.set(key, value)
    settings.save()

    return {
        "success": True,
        "extension": extension_name,
        "key": key,
        "message": f"Set {key} for {extension_name}",
    }
