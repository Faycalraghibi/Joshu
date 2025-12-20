"""
Agent Loader System for file-based agent discovery.

This module provides an extensible loader interface for discovering
and loading agent definitions from various sources like YAML, JSON,
or other formats.

Design:
- Loader -> Registry pattern
- Loader handles parsing and conversion
- Registry stays pure and validated
"""

from __future__ import annotations

import json
import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import List, Optional

from joshu.agents.definitions import AgentDefinition
from joshu.agents.exceptions import AgentValidationError

logger = logging.getLogger(__name__)


class AgentLoader(ABC):
    """
    Abstract base class for agent loaders.

    Loaders are responsible for discovering and parsing agent definitions
    from external sources. They return AgentDefinition instances that
    can be registered with the AgentRegistry.

    Subclasses must implement:
        - load_from_path(): Load agents from a file or directory path
        - supports_extension(): Check if loader supports a file extension
    """

    @abstractmethod
    def load_from_path(self, path: Path) -> List[AgentDefinition]:
        """
        Load agent definitions from a file or directory.

        Args:
            path: Path to file or directory containing agent definitions

        Returns:
            List of AgentDefinition instances

        Raises:
            FileNotFoundError: If path does not exist
            AgentValidationError: If agent definition is invalid
        """
        pass

    @abstractmethod
    def supports_extension(self, extension: str) -> bool:
        """
        Check if this loader supports the given file extension.

        Args:
            extension: File extension (e.g., ".yaml", ".json")

        Returns:
            True if loader can handle this extension
        """
        pass

    def load_from_string(self, content: str) -> List[AgentDefinition]:
        """
        Load agent definitions from a string.

        Default implementation raises NotImplementedError.
        Subclasses may override to support string parsing.

        Args:
            content: String content to parse

        Returns:
            List of AgentDefinition instances
        """
        raise NotImplementedError("String loading not supported by this loader")


class JsonAgentLoader(AgentLoader):
    """
    Loader for JSON-formatted agent definitions.

    Supports:
        - Single agent definition files
        - Arrays of agent definitions
        - Agent definition directories
    """

    def supports_extension(self, extension: str) -> bool:
        """Check if extension is .json."""
        return extension.lower() in (".json",)

    def load_from_path(self, path: Path) -> List[AgentDefinition]:
        """
        Load agent definitions from JSON file(s).

        Args:
            path: Path to JSON file or directory

        Returns:
            List of AgentDefinition instances
        """
        path = Path(path)

        if not path.exists():
            raise FileNotFoundError(f"Path does not exist: {path}")

        if path.is_file():
            return self._load_file(path)
        elif path.is_dir():
            return self._load_directory(path)
        else:
            raise ValueError(f"Path is neither file nor directory: {path}")

    def _load_file(self, file_path: Path) -> List[AgentDefinition]:
        """Load agents from a single JSON file."""
        logger.debug(f"Loading agents from JSON file: {file_path}")

        try:
            content = file_path.read_text(encoding="utf-8")
            return self.load_from_string(content)
        except json.JSONDecodeError as e:
            raise AgentValidationError(f"Invalid JSON in {file_path}: {e}") from e

    def _load_directory(self, dir_path: Path) -> List[AgentDefinition]:
        """Load agents from all JSON files in a directory."""
        agents = []
        for json_file in dir_path.glob("*.json"):
            try:
                agents.extend(self._load_file(json_file))
            except Exception as e:
                logger.error(f"Failed to load {json_file}: {e}")
        return agents

    def load_from_string(self, content: str) -> List[AgentDefinition]:
        """
        Load agent definitions from a JSON string.

        Args:
            content: JSON string (object or array)

        Returns:
            List of AgentDefinition instances
        """
        data = json.loads(content)

        if isinstance(data, list):
            # Array of agent definitions
            agents = []
            for item in data:
                agent = AgentDefinition.from_dict(item)
                if not agent.validate():
                    raise AgentValidationError(
                        f"Invalid agent definition: {item.get('name', 'unknown')}"
                    )
                agents.append(agent)
            return agents
        elif isinstance(data, dict):
            # Single agent definition
            agent = AgentDefinition.from_dict(data)
            if not agent.validate():
                raise AgentValidationError(
                    f"Invalid agent definition: {data.get('name', 'unknown')}"
                )
            return [agent]
        else:
            raise AgentValidationError(f"Expected JSON object or array, got {type(data).__name__}")


class YamlAgentLoader(AgentLoader):
    """
    Loader for YAML-formatted agent definitions.

    Supports:
        - Single agent definition files
        - Multi-document YAML files (--- separated)
        - Agent definition directories

    Requires PyYAML to be installed.
    """

    def __init__(self) -> None:
        """Initialize YAML loader, checking for PyYAML availability."""
        try:
            import yaml  # noqa: F401

            self._yaml_available = True
        except ImportError:
            self._yaml_available = False
            logger.warning("PyYAML not installed. YAML agent loading unavailable.")

    def supports_extension(self, extension: str) -> bool:
        """Check if extension is .yaml or .yml."""
        return extension.lower() in (".yaml", ".yml")

    def load_from_path(self, path: Path) -> List[AgentDefinition]:
        """
        Load agent definitions from YAML file(s).

        Args:
            path: Path to YAML file or directory

        Returns:
            List of AgentDefinition instances
        """
        if not self._yaml_available:
            raise ImportError(
                "PyYAML is required for YAML loading. Install with: pip install pyyaml"
            )

        path = Path(path)

        if not path.exists():
            raise FileNotFoundError(f"Path does not exist: {path}")

        if path.is_file():
            return self._load_file(path)
        elif path.is_dir():
            return self._load_directory(path)
        else:
            raise ValueError(f"Path is neither file nor directory: {path}")

    def _load_file(self, file_path: Path) -> List[AgentDefinition]:
        """Load agents from a single YAML file."""
        import yaml

        logger.debug(f"Loading agents from YAML file: {file_path}")

        try:
            content = file_path.read_text(encoding="utf-8")
            return self.load_from_string(content)
        except yaml.YAMLError as e:
            raise AgentValidationError(f"Invalid YAML in {file_path}: {e}") from e

    def _load_directory(self, dir_path: Path) -> List[AgentDefinition]:
        """Load agents from all YAML files in a directory."""
        agents = []
        for yaml_file in dir_path.glob("*.yaml"):
            try:
                agents.extend(self._load_file(yaml_file))
            except Exception as e:
                logger.error(f"Failed to load {yaml_file}: {e}")

        for yaml_file in dir_path.glob("*.yml"):
            try:
                agents.extend(self._load_file(yaml_file))
            except Exception as e:
                logger.error(f"Failed to load {yaml_file}: {e}")

        return agents

    def load_from_string(self, content: str) -> List[AgentDefinition]:
        """
        Load agent definitions from a YAML string.

        Supports multi-document YAML (--- separated).

        Args:
            content: YAML string

        Returns:
            List of AgentDefinition instances
        """
        import yaml

        agents = []

        # Load all documents (supports multi-doc YAML)
        for doc in yaml.safe_load_all(content):
            if doc is None:
                continue

            if isinstance(doc, list):
                for item in doc:
                    agent = AgentDefinition.from_dict(item)
                    if not agent.validate():
                        raise AgentValidationError(
                            f"Invalid agent definition: {item.get('name', 'unknown')}"
                        )
                    agents.append(agent)
            elif isinstance(doc, dict):
                agent = AgentDefinition.from_dict(doc)
                if not agent.validate():
                    raise AgentValidationError(
                        f"Invalid agent definition: {doc.get('name', 'unknown')}"
                    )
                agents.append(agent)

        return agents


class CompositeAgentLoader(AgentLoader):
    """
    Loader that delegates to specialized loaders based on file extension.

    Automatically selects the appropriate loader (JSON, YAML, etc.)
    based on file extension.
    """

    def __init__(self, loaders: Optional[List[AgentLoader]] = None) -> None:
        """
        Initialize with a list of loaders.

        Args:
            loaders: List of loaders to delegate to. Defaults to JSON and YAML loaders.
        """
        if loaders is None:
            self._loaders = [JsonAgentLoader(), YamlAgentLoader()]
        else:
            self._loaders = loaders

    def supports_extension(self, extension: str) -> bool:
        """Check if any loader supports this extension."""
        return any(loader.supports_extension(extension) for loader in self._loaders)

    def _get_loader(self, extension: str) -> Optional[AgentLoader]:
        """Get the appropriate loader for an extension."""
        for loader in self._loaders:
            if loader.supports_extension(extension):
                return loader
        return None

    def load_from_path(self, path: Path) -> List[AgentDefinition]:
        """
        Load agent definitions from path using appropriate loader.

        Args:
            path: Path to file or directory

        Returns:
            List of AgentDefinition instances
        """
        path = Path(path)

        if not path.exists():
            raise FileNotFoundError(f"Path does not exist: {path}")

        if path.is_file():
            loader = self._get_loader(path.suffix)
            if loader is None:
                raise ValueError(f"No loader available for extension: {path.suffix}")
            return loader.load_from_path(path)

        elif path.is_dir():
            # Load all supported files from directory
            agents = []
            for file_path in path.iterdir():
                if file_path.is_file():
                    loader = self._get_loader(file_path.suffix)
                    if loader:
                        try:
                            agents.extend(loader.load_from_path(file_path))
                        except Exception as e:
                            logger.error(f"Failed to load {file_path}: {e}")
            return agents

        else:
            raise ValueError(f"Path is neither file nor directory: {path}")


def load_agents_from_path(path: str | Path) -> List[AgentDefinition]:
    """
    Convenience function to load agents from a file or directory.

    Automatically selects the appropriate loader based on file extension.

    Args:
        path: Path to file or directory

    Returns:
        List of AgentDefinition instances

    Example:
        >>> agents = load_agents_from_path("agents/")
        >>> for agent in agents:
        ...     registry.register(agent)
    """
    loader = CompositeAgentLoader()
    return loader.load_from_path(Path(path))
