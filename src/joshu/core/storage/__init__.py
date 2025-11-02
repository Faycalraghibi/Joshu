"""Storage abstraction layer for Joshu Assistant.

This module provides a pluggable storage system that supports multiple backends:
- JSON file storage (default)

Future database backends (SQLite, PostgreSQL, etc.) can be added by implementing
the StorageBackend interface from base.py.
"""

from .base import StorageBackend, StorageEntry, QueryFilter, EntryType
from .json_file import JsonFileStorage

__all__ = ['StorageBackend', 'StorageEntry', 'QueryFilter', 'EntryType', 'JsonFileStorage']
