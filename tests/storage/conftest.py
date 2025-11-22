"""Shared fixtures and configuration for storage tests."""

import pytest
import tempfile
from pathlib import Path
from joshu.core.storage import JsonFileStorage


@pytest.fixture
def temp_storage():
    """Create a temporary JSON file storage for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        storage_path = Path(tmpdir) / 'test_storage.json'
        storage = JsonFileStorage(storage_path)
        yield storage


@pytest.fixture
def temp_storage_path():
    """Create a temporary storage file path for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        storage_path = Path(tmpdir) / 'test_storage.json'
        yield storage_path