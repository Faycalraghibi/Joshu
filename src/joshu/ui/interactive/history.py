"""Prompt history management with JSON storage support."""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import List, Optional

try:
    from prompt_toolkit.history import History as PTHistory

    PROMPT_TOOLKIT_AVAILABLE = True
except ImportError:
    PTHistory = object
    PROMPT_TOOLKIT_AVAILABLE = False

from joshu.core.storage import EntryType, JsonFileStorage, QueryFilter, StorageEntry

logger = logging.getLogger(__name__)


if PROMPT_TOOLKIT_AVAILABLE:

    class JsonHistory(PTHistory):
        """Prompt history backed by JSON storage instead of text file."""

        def __init__(self, storage_path: Optional[Path] = None):
            """
            Initialize JSON-backed prompt history.

            Args:
                storage_path: Path to JSON storage file. If None, uses .joshu_data.json
            """
            super().__init__()
            if storage_path is None:
                storage_path = Path.cwd() / "cache" / "joshu_data.json"

            self.storage = JsonFileStorage(storage_path)
            self._history_strings: List[str] = []
            self._load_history()

        def _load_history(self) -> None:
            """Load prompt history from JSON storage."""
            try:
                filter = QueryFilter(entry_type=EntryType.PROMPT_HISTORY, limit=1000)
                entries = self.storage.query_entries(filter)
                entries.sort(key=lambda x: x.timestamp, reverse=True)
                self._history_strings = [
                    entry.data.get("command", "") for entry in entries if entry.data.get("command")
                ]
                self._history_strings.reverse()
                logger.debug(
                    f"Loaded {len(self._history_strings)} prompt history entries from storage"
                )
            except Exception as e:
                logger.warning(f"Failed to load prompt history: {e}")
                self._history_strings = []

        def _save_to_storage(self, command: str) -> None:
            """Save a command to JSON storage."""
            try:
                entry = StorageEntry(
                    id=f"prompt_{int(time.time() * 1000000)}",
                    type=EntryType.PROMPT_HISTORY,
                    data={"command": command},
                    timestamp=time.time(),
                )
                self.storage.save_entry(entry)
            except Exception as e:
                logger.warning(f"Failed to save prompt history entry: {e}")

        def load_history_strings(self) -> List[str]:
            """Load all history strings."""
            return list(self._history_strings)

        def store_string(self, string: str) -> None:
            """Store a string in the history."""
            if string and string.strip():
                if self._history_strings and self._history_strings[-1] == string:
                    return

                self._history_strings.append(string)
                if len(self._history_strings) > 1000:
                    self._history_strings = self._history_strings[-1000:]

                self._save_to_storage(string)

else:
    # Fallback class if prompt_toolkit is not available
    class JsonHistoryFallback:
        """Fallback prompt history when prompt_toolkit is not available."""

        def __init__(self, storage_path: Optional[Path] = None):
            if storage_path is None:
                storage_path = Path.cwd() / "cache" / "joshu_data.json"
            self.storage = JsonFileStorage(storage_path)
            self._history_strings: List[str] = []
            self._load_history()

        def _load_history(self) -> None:
            """Load prompt history from JSON storage."""
            try:
                filter = QueryFilter(entry_type=EntryType.PROMPT_HISTORY, limit=1000)
                entries = self.storage.query_entries(filter)
                entries.sort(key=lambda x: x.timestamp, reverse=True)
                self._history_strings = [
                    entry.data.get("command", "") for entry in entries if entry.data.get("command")
                ]
                self._history_strings.reverse()
            except Exception:
                self._history_strings = []

        def load_history_strings(self) -> List[str]:
            return list(self._history_strings)

        def store_string(self, string: str) -> None:
            if string and string.strip():
                if self._history_strings and self._history_strings[-1] == string:
                    return
                self._history_strings.append(string)
                if len(self._history_strings) > 1000:
                    self._history_strings = self._history_strings[-1000:]
                self._save_to_storage(string)

        def _save_to_storage(self, command: str) -> None:
            try:
                entry = StorageEntry(
                    id=f"prompt_{int(time.time() * 1000000)}",
                    type=EntryType.PROMPT_HISTORY,
                    data={"command": command},
                    timestamp=time.time(),
                )
                self.storage.save_entry(entry)
            except Exception:
                pass
