"""Abstract base classes for storage backends."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional


class EntryType(Enum):
    """Type of storage entry."""

    CONVERSATION = "conversation"
    MEMORY = "memory"
    SESSION = "session"
    PROMPT_HISTORY = "prompt_history"


@dataclass
class StorageEntry:
    """Represents a single storage entry."""

    id: str
    type: EntryType
    data: Dict[str, Any]
    timestamp: float
    metadata: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert entry to dictionary."""
        return {
            "id": self.id,
            "type": self.type.value,
            "data": self.data,
            "timestamp": self.timestamp,
            "metadata": self.metadata or {},
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "StorageEntry":
        """Create entry from dictionary."""
        return cls(
            id=data["id"],
            type=EntryType(data["type"]),
            data=data["data"],
            timestamp=data["timestamp"],
            metadata=data.get("metadata"),
        )


@dataclass
class QueryFilter:
    """Filter criteria for querying entries."""

    entry_type: Optional[EntryType] = None
    session_id: Optional[str] = None
    role: Optional[str] = None
    mode: Optional[str] = None
    start_timestamp: Optional[float] = None
    end_timestamp: Optional[float] = None
    limit: Optional[int] = None
    offset: int = 0


class StorageBackend(ABC):
    """Abstract base class for storage backends."""

    @abstractmethod
    def save_entry(self, entry: StorageEntry) -> bool:
        """Save an entry to storage.

        Args:
            entry: The entry to save

        Returns:
            True if successful, False otherwise
        """
        pass

    @abstractmethod
    def get_entry(self, entry_id: str) -> Optional[StorageEntry]:
        """Get an entry by ID.

        Args:
            entry_id: The ID of the entry

        Returns:
            The entry if found, None otherwise
        """
        pass

    @abstractmethod
    def query_entries(self, filter: QueryFilter) -> List[StorageEntry]:
        """Query entries with filter criteria.

        Args:
            filter: Filter criteria

        Returns:
            List of matching entries
        """
        pass

    @abstractmethod
    def delete_entry(self, entry_id: str) -> bool:
        """Delete an entry by ID.

        Args:
            entry_id: The ID of the entry

        Returns:
            True if deleted, False otherwise
        """
        pass

    @abstractmethod
    def delete_entries(self, filter: QueryFilter) -> int:
        """Delete entries matching filter criteria.

        Args:
            filter: Filter criteria

        Returns:
            Number of entries deleted
        """
        pass

    @abstractmethod
    def count_entries(self, filter: QueryFilter) -> int:
        """Count entries matching filter criteria.

        Args:
            filter: Filter criteria

        Returns:
            Number of matching entries
        """
        pass

    @abstractmethod
    def close(self) -> None:
        """Close the storage backend and cleanup resources."""
        pass
