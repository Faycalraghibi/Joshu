"""
Configuration management for OpenCLI Assistant.
Handles user preferences, model settings, and other configurable options.
"""

from __future__ import annotations

import os
import yaml
import logging
from pathlib import Path
from typing import Dict, Any, Optional
from dataclasses import dataclass, asdict

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
    # Enhanced interactive mode settings
    "enhanced_interactive": True,
    "multiline_input": True,
    "vim_mode": False,
    "persistent_history": True,
    "history_limit": 1000,
}


@dataclass
class OpenCLIConfig:
    """OpenCLI Configuration Data Class"""
    model: str = "llama-3-8b"
    safety_mode: bool = True
    auto_execute: bool = False
    max_tokens: int = 4096
    temperature: float = 0.1
    history_size: int = 100
    log_level: str = "INFO"
    memory_enabled: bool = True
    sandbox_enabled: bool = True
    # Enhanced interactive mode settings
    enhanced_interactive: bool = True
    multiline_input: bool = True
    vim_mode: bool = False
    persistent_history: bool = True
    history_limit: int = 1000

    @classmethod
    def from_dict(cls, config_dict: Dict[str, Any]) -> "OpenCLIConfig":
        """Create OpenCLIConfig from dictionary, using defaults for missing values."""
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
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert OpenCLIConfig to dictionary."""
        return asdict(self)


class ConfigManager:
    """Manages OpenCLI configuration loading, saving, and access."""
    
    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize ConfigManager.
        
        Args:
            config_path: Path to config file. If None, uses default location.
        """
        if config_path is None:
            # Default config location: ~/.opencli/config.yaml
            home = Path.home()
            self.config_path = home / ".opencli" / "config.yaml"
        else:
            self.config_path = Path(config_path)
        
        self.config: OpenCLIConfig = OpenCLIConfig()
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
            with open(self.config_path, 'r') as f:
                config_data = yaml.safe_load(f) or {}
            
            # Create OpenCLIConfig from loaded data
            self.config = OpenCLIConfig.from_dict(config_data)
            logger.info(f"Configuration loaded from {self.config_path}")
            return True
            
        except Exception as e:
            logger.warning(f"Failed to load configuration: {e}")
            # Use default configuration
            self.config = OpenCLIConfig()
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
            with open(self.config_path, 'w') as f:
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
        self.config = OpenCLIConfig()
    
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
