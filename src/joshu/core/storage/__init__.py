"""Storage abstraction layer for Joshu Assistant.

This module provides a pluggable storage system that supports multiple backends:
- JSON file storage (default)
- Semantic memory (vector database for long-term conversation recall)

Future database backends (SQLite, PostgreSQL, etc.) can be added by implementing
the StorageBackend interface from base.py.
"""

from .base import EntryType, QueryFilter, StorageBackend, StorageEntry
from .json_file import JsonFileStorage

# Import semantic memory (optional, will handle missing dependencies gracefully)
try:
    from .semantic_memory import SemanticMemory, SemanticMemoryEntry

    __all__ = [
        "StorageBackend",
        "StorageEntry",
        "QueryFilter",
        "EntryType",
        "JsonFileStorage",
        "SemanticMemory",
        "SemanticMemoryEntry",
    ]
except ImportError:
    __all__ = ["StorageBackend", "StorageEntry", "QueryFilter", "EntryType", "JsonFileStorage"]
