"""JSON file-based storage backend."""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from .base import QueryFilter, StorageBackend, StorageEntry

logger = logging.getLogger(__name__)


class JsonFileStorage(StorageBackend):
    """JSON file-based storage implementation."""

    def __init__(self, storage_path: Optional[Path] = None):
        """
        Initialize JSON file storage.

        Args:
            storage_path: Path to the JSON storage file. If None, uses ~/.joshu/data.json.
        """
        if storage_path is None:
            from joshu.core.paths import joshu_home

            storage_path = joshu_home() / "data.json"

        self.storage_path = Path(storage_path)
        self._entries: List[StorageEntry] = []
        self._load_entries()

    def _load_entries(self) -> None:
        """Load entries from JSON file."""
        if not self.storage_path.exists():
            self._entries = []
            return

        try:
            with open(self.storage_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                self._entries = [StorageEntry.from_dict(entry) for entry in data.get("entries", [])]
            logger.debug(f"Loaded {len(self._entries)} entries from {self.storage_path}")
        except (json.JSONDecodeError, IOError, KeyError) as e:
            logger.warning(f"Failed to load entries from {self.storage_path}: {e}")
            self._entries = []

    def _save_entries(self) -> bool:
        """Save entries to JSON file."""
        try:
            # Ensure directory exists
            self.storage_path.parent.mkdir(parents=True, exist_ok=True)

            # Write to temporary file first, then rename (atomic write)
            temp_path = self.storage_path.with_suffix(".tmp.json")
            with open(temp_path, "w", encoding="utf-8") as f:
                json.dump(
                    {
                        "version": "1.0",
                        "updated_at": datetime.now().isoformat(),
                        "entries": [entry.to_dict() for entry in self._entries],
                    },
                    f,
                    indent=2,
                    ensure_ascii=False,
                )
                f.flush()
                os.fsync(f.fileno())

            # Atomic rename
            temp_path.replace(self.storage_path)
            logger.debug(f"Saved {len(self._entries)} entries to {self.storage_path}")
            return True
        except (IOError, OSError, PermissionError) as e:
            logger.error(f"Failed to save entries to {self.storage_path}: {e}")
            return False

    def save_entry(self, entry: StorageEntry) -> bool:
        """Save an entry to storage."""
        # Check if entry with same ID exists, update it
        existing_index = None
        for i, e in enumerate(self._entries):
            if e.id == entry.id:
                existing_index = i
                break

        if existing_index is not None:
            self._entries[existing_index] = entry
        else:
            self._entries.append(entry)

        return self._save_entries()

    def get_entry(self, entry_id: str) -> Optional[StorageEntry]:
        """Get an entry by ID."""
        for entry in self._entries:
            if entry.id == entry_id:
                return entry
        return None

    def query_entries(self, filter: QueryFilter) -> List[StorageEntry]:
        """Query entries with filter criteria."""
        results = []

        for entry in self._entries:
            # Filter by type
            if filter.entry_type and entry.type != filter.entry_type:
                continue

            # Filter by session_id (if present in metadata)
            if filter.session_id:
                entry_session = entry.metadata.get("session_id") if entry.metadata else None
                if entry_session is None or (
                    entry_session != filter.session_id
                    and not entry_session.startswith(filter.session_id)
                ):
                    continue

            # Filter by role (for conversation entries)
            if filter.role and entry.data.get("role") != filter.role:
                continue

            # Filter by mode (if present in metadata)
            if filter.mode:
                entry_mode = entry.metadata.get("mode") if entry.metadata else None
                if entry_mode != filter.mode:
                    continue

            # Filter by timestamp range
            if filter.start_timestamp and entry.timestamp < filter.start_timestamp:
                continue

            if filter.end_timestamp and entry.timestamp > filter.end_timestamp:
                continue

            results.append(entry)

        # Sort by timestamp (newest first)
        results.sort(key=lambda x: x.timestamp, reverse=True)

        # Apply limit and offset
        if filter.offset > 0:
            results = results[filter.offset :]

        if filter.limit:
            results = results[: filter.limit]

        return results

    def delete_entry(self, entry_id: str) -> bool:
        """Delete an entry by ID."""
        original_count = len(self._entries)
        self._entries = [e for e in self._entries if e.id != entry_id]

        if len(self._entries) < original_count:
            return self._save_entries()
        return False

    def delete_entries(self, filter: QueryFilter) -> int:
        """Delete entries matching filter criteria."""
        matching_ids = {e.id for e in self.query_entries(filter)}
        original_count = len(self._entries)
        self._entries = [e for e in self._entries if e.id not in matching_ids]

        deleted_count = original_count - len(self._entries)
        if deleted_count > 0:
            self._save_entries()

        return deleted_count

    def count_entries(self, filter: QueryFilter) -> int:
        """Count entries matching filter criteria."""
        return len(self.query_entries(filter))

    def close(self) -> None:
        """Close the storage backend."""
        # Save any pending changes
        self._save_entries()
        logger.debug("JSON file storage closed")
