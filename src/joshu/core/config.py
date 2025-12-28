"""
Configuration management for Joshu Assistant.
Handles user preferences, model settings, and other configurable options.
"""

from __future__ import annotations

import logging
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, Optional

import yaml

logger = logging.getLogger(__name__)

# Default configuration
DEFAULT_CONFIG = {
    "model": "llama-3-8b",
    "safety_mode": True,
    "auto_execute": False,
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
    # Translation cache settings
    "cache_enabled": True,
    "cache_similarity_threshold": 0.85,
    "cache_max_entries": 1000,
    "cache_dir": "./cache",
    # Attention mechanism settings
    "attention_enabled": True,
    "attention_similarity_weight": 0.8,
    "attention_recency_weight": 0.2,
    "max_context_turns": 10,
    # Auto-fix settings
    "auto_fix_enabled": True,
    "auto_fix_max_attempts": 2,
    "auto_fix_require_approval": None,  # If None, inherits from auto_execute
    # Web search settings
    "web_search_enabled": True,
    "web_search_max_results": 5,
    "web_search_timeout": 10,
    # Tool calling settings
    "tool_calling_enabled": True,
    "tool_calling_max_iterations": 3,
    "web_search_tool_enabled": True,
    # MCP Server settings
    "mcp_enabled": True,
    "mcp_discovery_on_startup": True,
    "mcp_servers": {},
}


@dataclass
class JoshuConfig:
    """Joshu Configuration Data Class"""

    model: str = "llama-3-8b"
    safety_mode: bool = True
    auto_execute: bool = False
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
    # Translation cache settings
    cache_enabled: bool = True
    cache_similarity_threshold: float = 0.85
    cache_max_entries: int = 1000
    cache_dir: str = "./cache"
    # Attention mechanism settings
    attention_enabled: bool = True
    attention_similarity_weight: float = 0.8
    attention_recency_weight: float = 0.2
    max_context_turns: int = 10
    # Auto-fix settings
    auto_fix_enabled: bool = True
    auto_fix_max_attempts: int = 2
    auto_fix_require_approval: Optional[bool] = None
    # Web search settings
    web_search_enabled: bool = True
    web_search_max_results: int = 5
    web_search_timeout: int = 10
    # Tool calling settings
    tool_calling_enabled: bool = True
    tool_calling_max_iterations: int = 3
    web_search_tool_enabled: bool = True
    # MCP Server settings
    mcp_enabled: bool = True
    mcp_discovery_on_startup: bool = True
    mcp_servers: Dict[str, Any] = None  # type: ignore  # Will use default_factory in post_init

    @classmethod
    def from_dict(cls, config_dict: Dict[str, Any]) -> "JoshuConfig":
        """Create JoshuConfig from dictionary, using defaults for missing values."""
        # Use defaults for missing keys
        for key, default_value in DEFAULT_CONFIG.items():
            if key not in config_dict:
                config_dict[key] = default_value

        return cls(
            model=config_dict.get("model", DEFAULT_CONFIG["model"]),
            safety_mode=config_dict.get("safety_mode", DEFAULT_CONFIG["safety_mode"]),
            auto_execute=config_dict.get("auto_execute", DEFAULT_CONFIG["auto_execute"]),
            max_tokens=config_dict.get("max_tokens", DEFAULT_CONFIG["max_tokens"]),
            temperature=config_dict.get("temperature", DEFAULT_CONFIG["temperature"]),
            history_size=config_dict.get("history_size", DEFAULT_CONFIG["history_size"]),
            log_level=config_dict.get("log_level", DEFAULT_CONFIG["log_level"]),
            memory_enabled=config_dict.get("memory_enabled", DEFAULT_CONFIG["memory_enabled"]),
            sandbox_enabled=config_dict.get("sandbox_enabled", DEFAULT_CONFIG["sandbox_enabled"]),
            # interactive mode settings
            interactive=config_dict.get("interactive", DEFAULT_CONFIG["interactive"]),
            multiline_input=config_dict.get("multiline_input", DEFAULT_CONFIG["multiline_input"]),
            vim_mode=config_dict.get("vim_mode", DEFAULT_CONFIG["vim_mode"]),
            persistent_history=config_dict.get(
                "persistent_history", DEFAULT_CONFIG["persistent_history"]
            ),
            history_limit=config_dict.get("history_limit", DEFAULT_CONFIG["history_limit"]),
            # Semantic memory settings
            semantic_memory_enabled=config_dict.get(
                "semantic_memory_enabled", DEFAULT_CONFIG["semantic_memory_enabled"]
            ),
            semantic_memory_similarity_threshold=config_dict.get(
                "semantic_memory_similarity_threshold",
                DEFAULT_CONFIG["semantic_memory_similarity_threshold"],
            ),
            semantic_memory_max_results=config_dict.get(
                "semantic_memory_max_results", DEFAULT_CONFIG["semantic_memory_max_results"]
            ),
            semantic_memory_min_content_length=config_dict.get(
                "semantic_memory_min_content_length",
                DEFAULT_CONFIG["semantic_memory_min_content_length"],
            ),
            # Translation cache settings
            cache_enabled=config_dict.get("cache_enabled", DEFAULT_CONFIG["cache_enabled"]),
            cache_similarity_threshold=config_dict.get(
                "cache_similarity_threshold", DEFAULT_CONFIG["cache_similarity_threshold"]
            ),
            cache_max_entries=config_dict.get(
                "cache_max_entries", DEFAULT_CONFIG["cache_max_entries"]
            ),
            cache_dir=config_dict.get("cache_dir", DEFAULT_CONFIG["cache_dir"]),
            # Attention mechanism settings
            attention_enabled=config_dict.get(
                "attention_enabled", DEFAULT_CONFIG["attention_enabled"]
            ),
            attention_similarity_weight=config_dict.get(
                "attention_similarity_weight", DEFAULT_CONFIG["attention_similarity_weight"]
            ),
            attention_recency_weight=config_dict.get(
                "attention_recency_weight", DEFAULT_CONFIG["attention_recency_weight"]
            ),
            max_context_turns=config_dict.get(
                "max_context_turns", DEFAULT_CONFIG["max_context_turns"]
            ),
            # Auto-fix settings
            auto_fix_enabled=config_dict.get(
                "auto_fix_enabled", DEFAULT_CONFIG["auto_fix_enabled"]
            ),
            auto_fix_max_attempts=config_dict.get(
                "auto_fix_max_attempts", DEFAULT_CONFIG["auto_fix_max_attempts"]
            ),
            auto_fix_require_approval=config_dict.get(
                "auto_fix_require_approval", DEFAULT_CONFIG["auto_fix_require_approval"]
            ),
            # Web search settings
            web_search_enabled=config_dict.get(
                "web_search_enabled", DEFAULT_CONFIG["web_search_enabled"]
            ),
            web_search_max_results=config_dict.get(
                "web_search_max_results", DEFAULT_CONFIG["web_search_max_results"]
            ),
            web_search_timeout=config_dict.get(
                "web_search_timeout", DEFAULT_CONFIG["web_search_timeout"]
            ),
            # Tool calling settings
            tool_calling_enabled=config_dict.get(
                "tool_calling_enabled", DEFAULT_CONFIG["tool_calling_enabled"]
            ),
            tool_calling_max_iterations=config_dict.get(
                "tool_calling_max_iterations", DEFAULT_CONFIG["tool_calling_max_iterations"]
            ),
            web_search_tool_enabled=config_dict.get(
                "web_search_tool_enabled", DEFAULT_CONFIG["web_search_tool_enabled"]
            ),
            # MCP Server settings
            mcp_enabled=config_dict.get("mcp_enabled", DEFAULT_CONFIG["mcp_enabled"]),
            mcp_discovery_on_startup=config_dict.get(
                "mcp_discovery_on_startup", DEFAULT_CONFIG["mcp_discovery_on_startup"]
            ),
            mcp_servers=config_dict.get("mcp_servers", DEFAULT_CONFIG["mcp_servers"]),
        )

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
            True if value was set successfully, False otherwise.
        """
        if hasattr(self.config, key):
            setattr(self.config, key, value)
            return True
        return False

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
