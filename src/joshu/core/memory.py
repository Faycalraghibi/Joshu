"""Memory store with storage backend support."""

from __future__ import annotations

import uuid
import time
import logging
from typing import Dict, Optional
from pathlib import Path

from .storage import StorageBackend, StorageEntry, EntryType, JsonFileStorage

logger = logging.getLogger(__name__)


class MemoryStore:
    """Memory store that can use different storage backends."""
    
    def __init__(self, storage_backend: Optional[StorageBackend] = None) -> None:
        """
        Initialize memory store.
        
        Args:
            storage_backend: Storage backend to use. If None, creates a JsonFileStorage.
        """
        if storage_backend is None:
            storage_backend = JsonFileStorage(Path.cwd() / '.joshu_memory.json')
        
        self.storage = storage_backend
        self._cache: Dict[str, str] = {}  # In-memory cache for fast access
        self._load_cache()
    
    def _load_cache(self) -> None:
        """Load memory entries from storage into cache."""
        from .storage import QueryFilter
        
        try:
            filter = QueryFilter(entry_type=EntryType.MEMORY)
            entries = self.storage.query_entries(filter)
            self._cache = {entry.data["key"]: entry.data["value"] for entry in entries}
            logger.debug(f"Loaded {len(self._cache)} memory entries from storage")
        except Exception as e:
            logger.warning(f"Failed to load memory cache: {e}")
            self._cache = {}
    
    def get(self, key: str) -> Optional[str]:
        """Get a value from memory."""
        # Check cache first
        if key in self._cache:
            return self._cache[key]
        
        # Try to load from storage
        try:
            from .storage import QueryFilter
            
            filter = QueryFilter(entry_type=EntryType.MEMORY)
            entries = self.storage.query_entries(filter)
            for entry in entries:
                if entry.data.get("key") == key:
                    value = entry.data.get("value")
                    self._cache[key] = value
                    return value
        except Exception as e:
            logger.warning(f"Failed to get memory entry from storage: {e}")
        
        return None
    
    def set(self, key: str, value: str) -> None:
        """Set a value in memory."""
        self._cache[key] = value
        
        # Save to storage
        try:
            entry = StorageEntry(
                id=str(uuid.uuid4()),
                type=EntryType.MEMORY,
                data={"key": key, "value": value},
                timestamp=time.time(),
                metadata={"key": key}
            )
            self.storage.save_entry(entry)
        except Exception as e:
            logger.warning(f"Failed to save memory entry to storage: {e}")
    
    def delete(self, key: str) -> bool:
        """Delete a key from memory."""
        if key in self._cache:
            del self._cache[key]
        
        # Delete from storage
        try:
            from .storage import QueryFilter
            
            filter = QueryFilter(
                entry_type=EntryType.MEMORY,
                limit=None
            )
            entries = self.storage.query_entries(filter)
            for entry in entries:
                if entry.data.get("key") == key:
                    return self.storage.delete_entry(entry.id)
        except Exception as e:
            logger.warning(f"Failed to delete memory entry from storage: {e}")
        
        return False
    
    def clear(self) -> None:
        """Clear all memory entries."""
        self._cache.clear()
        
        # Clear from storage
        try:
            from .storage import QueryFilter
            
            filter = QueryFilter(entry_type=EntryType.MEMORY)
            self.storage.delete_entries(filter)
        except Exception as e:
            logger.warning(f"Failed to clear memory entries from storage: {e}")
    
    @property
    def kv(self) -> Dict[str, str]:
        """Get the key-value cache (for backward compatibility)."""
        return self._cache


