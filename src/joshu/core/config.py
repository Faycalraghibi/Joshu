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
    "theme": "dark",
    "output_style": "default",
    "statusline": "",
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
    "defer_mcp_tools": "auto",
    "protected_paths": [],
    "allow_paths": [],
    "mask_secrets": True,
    "parallel_tools": True,
    "lsp": {},
    "mcp_discovery_on_startup": True,
    "mcp_servers": {},
    # Model provider settings (see joshu.core.providers)
    "provider": "openrouter",
    "providers": {},
    "fallback_providers": [],
    "auto_memory": True,
    "request_timeout": 120,
    "request_retries": 3,
    # Agent loop settings
    "agent_max_turns": 50,
    "permission_mode": "default",
    "context_window": 128000,
    "compact_threshold": 0.8,
    "tool_output_limit": 16000,
    "clear_tool_results_at": 60000,
    "save_sessions": True,
    "hooks": {},
    "model_pricing": {},
    "trusted_projects": [],
    "models": {},
    "permissions": {"allow": [], "deny": []},
    "diagnostics_enabled": True,
    "diagnostics": {},
    "shell_sandbox": {"mode": "off"},
}


TRI_STATE_KEYS = {"defer_mcp_tools"}


def _coerce_config_value(key: str, value: Any) -> Tuple[bool, Any]:
    """
    Check a value against the type of its default and coerce compatible numbers.

    Returns:
        (is_valid, coerced_value). Keys without a known default pass through unchanged.
    """
    if key not in DEFAULT_CONFIG:
        return True, value

    default = DEFAULT_CONFIG[key]

    # lsp: false, or {language: command}
    if key == "lsp":
        return value is False or value is True or isinstance(value, dict), value

    # auto / always / never settings that also accept true / false
    if key in TRI_STATE_KEYS:
        if isinstance(value, bool):
            return True, "always" if value else "never"
        text = str(value).strip().lower()
        aliases = {"true": "always", "false": "never", "on": "always", "off": "never"}
        text = aliases.get(text, text)
        return text in ("auto", "always", "never"), text

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
    theme: str = "dark"
    output_style: str = "default"
    statusline: str = ""
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
    defer_mcp_tools: str = "auto"
    protected_paths: List[str] = field(default_factory=list)
    allow_paths: List[str] = field(default_factory=list)
    mask_secrets: bool = True
    parallel_tools: bool = True
    lsp: Any = field(default_factory=dict)
    mcp_discovery_on_startup: bool = True
    mcp_servers: Dict[str, Any] = field(default_factory=dict)
    # Model provider settings (see joshu.core.providers)
    provider: str = "openrouter"
    providers: Dict[str, Any] = field(default_factory=dict)
    fallback_providers: List[str] = field(default_factory=list)
    auto_memory: bool = True
    request_timeout: float = 120
    request_retries: int = 3
    # Agent loop settings
    agent_max_turns: int = 50
    permission_mode: str = "default"
    context_window: int = 128000
    compact_threshold: float = 0.8
    tool_output_limit: int = 16000
    clear_tool_results_at: int = 60000
    save_sessions: bool = True
    hooks: Dict[str, Any] = field(default_factory=dict)
    model_pricing: Dict[str, Any] = field(default_factory=dict)
    trusted_projects: List[str] = field(default_factory=list)
    models: Dict[str, Any] = field(default_factory=dict)
    permissions: Dict[str, Any] = field(default_factory=lambda: {"allow": [], "deny": []})
    diagnostics_enabled: bool = True
    diagnostics: Dict[str, Any] = field(default_factory=dict)
    shell_sandbox: Dict[str, Any] = field(default_factory=lambda: {"mode": "off"})

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


PROJECT_CONFIG = Path(".joshu") / "config.yaml"
# Settings a project config may not change, whether trusted or not
USER_ONLY_KEYS = {"trusted_projects"}


def install_config_path() -> Path:
    """config/config.yaml in a source checkout (absent in a regular pip install)."""
    return Path(__file__).resolve().parents[3] / "config" / "config.yaml"


def user_config_path() -> Path:
    from joshu.core.paths import joshu_home

    return joshu_home() / "config.yaml"


def find_project_config(start: Optional[Path] = None) -> Optional[Path]:
    """The nearest .joshu/config.yaml at or above `start` (not the user config)."""
    user_config = user_config_path().resolve()
    home = Path.home().resolve()
    current = (start or Path.cwd()).resolve()
    for directory in [current, *current.parents]:
        if directory == home:
            # ~/.joshu is Joshu's default data directory, never a project
            return None
        candidate = directory / PROJECT_CONFIG
        if candidate.is_file():
            if candidate.resolve() == user_config:
                return None
            return candidate
    return None


def _same_path(a: str, b: Path) -> bool:
    try:
        return Path(a).expanduser().resolve() == b.resolve()
    except (OSError, ValueError):
        return False


class ConfigManager:
    """
    Loads and saves Joshu configuration.

    With an explicit path, that single file is the whole configuration (the
    original behaviour, used by tests and tools). Otherwise settings are
    layered, later layers winning:

        1. built-in defaults
        2. config/config.yaml in a source checkout (read-only)
        3. ~/.joshu/config.yaml, the user config; `joshu config --set` writes here
        4. .joshu/config.yaml in the project (nearest one above the current
           directory), only if the project is trusted (`joshu trust`), because
           a project config can run commands (hooks, diagnostics) and choose
           where code and API keys are sent (providers)
    """

    def __init__(self, config_path: Optional[str] = None):
        """
        Args:
            config_path: Use this single file instead of the layered setup.
        """
        self.layered = config_path is None
        self.config_path = user_config_path() if self.layered else Path(config_path)
        self.layers: List[Tuple[str, Path]] = []
        self.untrusted_project_config: Optional[Path] = None
        self._layer_data: List[Dict[str, Any]] = []
        self._user_data: Dict[str, Any] = {}
        self._project_data: Dict[str, Any] = {}
        self.config: JoshuConfig = JoshuConfig()
        self.load_config()

    # ---------------------------------------------------------------- load

    def load_config(self) -> bool:
        """Load configuration. Returns False if a file couldn't be read."""
        if not self.layered:
            return self._load_single_file()

        ok = True
        self.layers = []
        self._layer_data = []
        self.untrusted_project_config = None

        install = install_config_path()
        if install.is_file():
            data, read_ok = self._read(install)
            ok &= read_ok
            self._layer_data.append(data)
            self.layers.append(("install", install))

        user_data, read_ok = (
            self._read(self.config_path) if self.config_path.is_file() else ({}, True)
        )
        ok &= read_ok
        self._user_data = user_data
        if self.config_path.is_file():
            self.layers.append(("user", self.config_path))

        project = find_project_config()
        if project is not None:
            trusted = self._effective_value("trusted_projects") or []
            if any(_same_path(str(p), project.parent.parent) for p in trusted):
                data, read_ok = self._read(project)
                ok &= read_ok
                self._project_data = {k: v for k, v in data.items() if k not in USER_ONLY_KEYS}
                self.layers.append(("project", project))
            else:
                self._project_data = {}
                self.untrusted_project_config = project
        else:
            self._project_data = {}

        self._rebuild()
        return ok

    def _effective_value(self, key: str) -> Any:
        value = DEFAULT_CONFIG.get(key)
        for data in [*self._layer_data, self._user_data]:
            if key in data:
                value = data[key]
        return value

    def _rebuild(self) -> None:
        merged: Dict[str, Any] = {}
        for data in [*self._layer_data, self._user_data, self._project_data]:
            merged.update(data)
        self.config = JoshuConfig.from_dict(merged)

    def _read(self, path: Path) -> Tuple[Dict[str, Any], bool]:
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except Exception as e:
            logger.warning(f"Could not read {path}: {e}")
            return {}, False
        if not isinstance(data, dict):
            logger.warning(f"{path} must contain a mapping of settings")
            return {}, False
        return data, True

    def _load_single_file(self) -> bool:
        try:
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            if not self.config_path.exists():
                self.save_config()
                return True
            with open(self.config_path, "r") as f:
                config_data = yaml.safe_load(f) or {}
            self.config = JoshuConfig.from_dict(config_data)
            logger.info(f"Configuration loaded from {self.config_path}")
            return True
        except Exception as e:
            logger.warning(f"Failed to load configuration: {e}")
            self.config = JoshuConfig()
            return False

    # ---------------------------------------------------------------- save

    def save_config(self) -> bool:
        """
        Save configuration. In layered mode only the settings set in the user
        config are written, so defaults and other layers aren't frozen in.
        """
        try:
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            data = self._user_data if self.layered else self.config.to_dict()
            with open(self.config_path, "w") as f:
                yaml.dump(data, f, default_flow_style=False, sort_keys=False)
            logger.info(f"Configuration saved to {self.config_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to save configuration: {e}")
            return False

    # ------------------------------------------------------------- access

    def get(self, key: str, default: Any = None) -> Any:
        """Configuration value by key, or `default` for unknown keys."""
        return getattr(self.config, key, default)

    def set(self, key: str, value: Any) -> bool:
        """
        Set a configuration value (for this process; save_config persists it).

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
        if self.layered:
            self._user_data[key] = coerced
        return True

    def reset_to_defaults(self) -> None:
        """Forget the user's settings (other layers still apply)."""
        if self.layered:
            self._user_data = {}
            self._rebuild()
        else:
            self.config = JoshuConfig()

    def get_config_path(self) -> Path:
        """The file `save_config` writes (the user config in layered mode)."""
        return self.config_path

    # -------------------------------------------------------------- trust

    def trust_project(self, directory: Path) -> None:
        """Let `directory`'s .joshu/config.yaml apply (persisted in the user config)."""
        trusted = [str(p) for p in (self.get("trusted_projects") or [])]
        if not any(_same_path(p, directory) for p in trusted):
            trusted.append(str(directory.resolve()))
        self.set("trusted_projects", trusted)

    def untrust_project(self, directory: Path) -> bool:
        trusted = [str(p) for p in (self.get("trusted_projects") or [])]
        kept = [p for p in trusted if not _same_path(p, directory)]
        self.set("trusted_projects", kept)
        return len(kept) != len(trusted)


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
