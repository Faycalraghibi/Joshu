"""Shared fixtures and configuration for interactive mode tests."""

import pytest
from unittest.mock import MagicMock


@pytest.fixture
def mock_interactive_mode():
    """Create a mocked InteractiveMode instance for testing."""
    mode = MagicMock()
    mode.model = "test-model"
    mode.sandbox = False
    mode.verbose = False
    mode._show_message = MagicMock()
    return mode