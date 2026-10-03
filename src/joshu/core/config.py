"""
Configuration management for Joshu Assistant.
Handles user preferences, model settings, and other configurable options.
"""

from __future__ import annotations

import copy
import logging
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml

logger = logging.getLogger(__name__)

# Default configuration
DEFAULT_CONFIG = {
    "model": "poolside/laguna-s-2.1:free",
    "max_tokens": 4096,
    "temperature": 0.1,
    "history_size": 100,
    "log_level": "INFO",
    "memory_enabled": True,
    "sandbox_enabled": True,
    # interactive mode settings
    "interactive": True,
    "multiline_input": True,
    "vim_mode": False,
    "persistent_history": True,
    "history_limit": 1000,
    # Semantic memory settings
    "semantic_memory_enabled": True,
    "semantic_memory_similarity_threshold": 0.3,
    "semantic_memory_max_results": 5,
    "semantic_memory_min_content_length": 10,
    # Attention mechanism settings
    "attention_enabled": True,
    "attention_similarity_weight": 0.8,
    "attention_recency_weight": 0.2,
    "max_context_turns": 10,
    # Web search settings
    "web_search_enabled": True,
    "web_search_max_results": 5,
    "web_search_timeout": 10,
    # MCP Server settings
    "mcp_enabled": True,
    "mcp_discovery_on_startup": True,
    "mcp_servers": {},
    # Model provider settings (see joshu.core.providers)
    "provider": "openrouter",
    "providers": {},
    "fallback_providers": [],
    # Agent loop settings
    "agent_max_turns": 50,
    "permission_mode": "default",
    "context_window": 128000,
    "compact_threshold": 0.8,
    "tool_output_limit": 30000,
    "save_sessions": True,
    "hooks": {},
}


def _coerce_config_value(key: str, value: Any) -> Tuple[bool, Any]:
    """
    Check a value against the type of its default and coerce compatible numbers.

    Returns:
        (is_valid, coerced_value). Keys without a known default pass through unchanged.
    """
    if key not in DEFAULT_CONFIG:
        return True, value

    default = DEFAULT_CONFIG[key]

    # Optional[bool] settings (default None)
    if default is None:
        return value is None or isinstance(value, bool), value

    if isinstance(default, bool):
        return isinstance(value, bool), value

    if isinstance(default, int):
        if isinstance(value, bool):
            return False, value
        if isinstance(value, int):
            return True, value
        if isinstance(value, float) and value.is_integer():
            return True, int(value)
        return False, value

    if isinstance(default, float):
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return True, float(value)
        return False, value

    return isinstance(value, type(default)), value


@dataclass
class JoshuConfig:
    """Joshu Configuration Data Class"""

    model: str = "poolside/laguna-s-2.1:free"
    max_tokens: int = 4096
    temperature: float = 0.1
    history_size: int = 100
    log_level: str = "INFO"
    memory_enabled: bool = True
    sandbox_enabled: bool = True
    # interactive mode settings
    interactive: bool = True
    multiline_input: bool = True
    vim_mode: bool = False
    persistent_history: bool = True
    history_limit: int = 1000
    # Semantic memory settings
    semantic_memory_enabled: bool = True
    semantic_memory_similarity_threshold: float = 0.3
    semantic_memory_max_results: int = 5
    semantic_memory_min_content_length: int = 10
    # Attention mechanism settings
    attention_enabled: bool = True
    attention_similarity_weight: float = 0.8
    attention_recency_weight: float = 0.2
    max_context_turns: int = 10
    # Web search settings
    web_search_enabled: bool = True
    web_search_max_results: int = 5
    web_search_timeout: int = 10
    # MCP Server settings
    mcp_enabled: bool = True
    mcp_discovery_on_startup: bool = True
    mcp_servers: Dict[str, Any] = field(default_factory=dict)
    # Model provider settings (see joshu.core.providers)
    provider: str = "openrouter"
    providers: Dict[str, Any] = field(default_factory=dict)
    fallback_providers: List[str] = field(default_factory=list)
    # Agent loop settings
    agent_max_turns: int = 50
    permission_mode: str = "default"
    context_window: int = 128000
    compact_threshold: float = 0.8
    tool_output_limit: int = 30000
    save_sessions: bool = True
    hooks: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, config_dict: Dict[str, Any]) -> "JoshuConfig":
        """Create JoshuConfig from dictionary, using defaults for missing values."""
        # Use defaults for missing keys
        for key, default_value in DEFAULT_CONFIG.items():
            if key not in config_dict:
                config_dict[key] = copy.deepcopy(default_value)
                continue

            is_valid, coerced = _coerce_config_value(key, config_dict[key])
            if is_valid:
                config_dict[key] = coerced
            else:
                logger.warning(
                    f"Invalid value for '{key}': {config_dict[key]!r}; "
                    f"using default {default_value!r}"
                )
                config_dict[key] = copy.deepcopy(default_value)

        return cls(**{key: config_dict[key] for key in DEFAULT_CONFIG})

    def to_dict(self) -> Dict[str, Any]:
        """Convert JoshuConfig to dictionary."""
        return asdict(self)


class ConfigManager:
    """Manages Joshu configuration loading, saving, and access."""

    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize ConfigManager.

        Args:
            config_path: Path to config file. If None, uses default location.
        """
        if config_path is None:
            # Default config location: project's config/config.yaml
            # Get the project root (4 levels up from this file)
            project_root = Path(__file__).parent.parent.parent.parent
            self.config_path = project_root / "config" / "config.yaml"
        else:
            self.config_path = Path(config_path)

        self.config: JoshuConfig = JoshuConfig()
        self.load_config()

    def load_config(self) -> bool:
        """
        Load configuration from file.

        Returns:
            True if config was loaded successfully, False otherwise.
        """
        try:
            # Create config directory if it doesn't exist
            self.config_path.parent.mkdir(parents=True, exist_ok=True)

            # If config file doesn't exist, create it with defaults
            if not self.config_path.exists():
                self.save_config()
                return True

            # Load config from file
            with open(self.config_path, "r") as f:
                config_data = yaml.safe_load(f) or {}

            # Create JoshuConfig from loaded data
            self.config = JoshuConfig.from_dict(config_data)
            logger.info(f"Configuration loaded from {self.config_path}")
            return True

        except Exception as e:
            logger.warning(f"Failed to load configuration: {e}")
            # Use default configuration
            self.config = JoshuConfig()
            return False

    def save_config(self) -> bool:
        """
        Save current configuration to file.

        Returns:
            True if config was saved successfully, False otherwise.
        """
        try:
            # Create config directory if it doesn't exist
            self.config_path.parent.mkdir(parents=True, exist_ok=True)

            # Save config to file
            with open(self.config_path, "w") as f:
                yaml.dump(self.config.to_dict(), f, default_flow_style=False, sort_keys=False)

            logger.info(f"Configuration saved to {self.config_path}")
            return True

        except Exception as e:
            logger.error(f"Failed to save configuration: {e}")
            return False

    def get(self, key: str, default: Any = None) -> Any:
        """
        Get configuration value by key.

        Args:
            key: Configuration key
            default: Default value if key not found

        Returns:
            Configuration value or default.
        """
        return getattr(self.config, key, default)

    def set(self, key: str, value: Any) -> bool:
        """
        Set configuration value by key.

        Args:
            key: Configuration key
            value: Configuration value

        Returns:
            True if value was set successfully, False if the key is unknown
            or the value has the wrong type.
        """
        if not hasattr(self.config, key):
            return False

        is_valid, coerced = _coerce_config_value(key, value)
        if not is_valid:
            return False

        setattr(self.config, key, coerced)
        return True

    def reset_to_defaults(self) -> None:
        """Reset configuration to default values."""
        self.config = JoshuConfig()

    def get_config_path(self) -> Path:
        """Get the path to the configuration file."""
        return self.config_path


def get_config_manager() -> ConfigManager:
    """
    Get the global configuration manager instance.

    Returns:
        ConfigManager instance.
    """
    global _config_manager_instance
    if _config_manager_instance is None:
        _config_manager_instance = ConfigManager()
    return _config_manager_instance


# Module-level variable to store the singleton instance
_config_manager_instance: ConfigManager | None = None
