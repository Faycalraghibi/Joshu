"""Shared fixtures and configuration for interactive mode tests."""

from unittest.mock import MagicMock

import pytest


@pytest.fixture
def mock_interactive_mode():
    """Create a mocked InteractiveMode instance for testing."""
    mode = MagicMock()
    mode.model = "test-model"
    mode.sandbox = False
    mode.verbose = False
    mode._show_message = MagicMock()
    return mode
