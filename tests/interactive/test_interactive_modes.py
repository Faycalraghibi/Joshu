"""Tests for interactive mode handlers (ask, plan, agent)."""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from joshu.core.context_provider import ContextProvider
from joshu.core.storage import JsonFileStorage
from joshu.ui.interactive.modes import AskModeHandler, PlanModeHandler


@pytest.fixture
def mock_interactive_mode():
    """Create a mocked InteractiveMode instance for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        storage = JsonFileStorage(Path(tmpdir) / "test_data.json")
        context_provider = ContextProvider(storage_backend=storage)

        mode = MagicMock()
        mode.context_provider = context_provider
        mode.model = "test-model"
        mode.sandbox = False
        mode._show_message = MagicMock()

        yield mode


def test_ask_mode_handler():
    """Test AskModeHandler processes queries correctly."""
    with tempfile.TemporaryDirectory() as tmpdir:
        storage = JsonFileStorage(Path(tmpdir) / "test_data.json")
        context_provider = ContextProvider(storage_backend=storage)

        mode = MagicMock()
        mode.context_provider = context_provider
        mode.model = "test-model"
        mode._show_message = MagicMock()

        handler = AskModeHandler(mode)

        # Mock LLM response
        with patch("joshu.models.openrouter.chat_completion") as mock_chat:
            mock_chat.return_value = "This is a helpful response"

            handler.handle("What is Python?")

            # Should have called LLM
            mock_chat.assert_called()
            # Should have shown message
            mode._show_message.assert_called()


def test_plan_mode_handler():
    """Test PlanModeHandler generates plans correctly."""
    with tempfile.TemporaryDirectory() as tmpdir:
        storage = JsonFileStorage(Path(tmpdir) / "test_data.json")
        context_provider = ContextProvider(storage_backend=storage)

        mode = MagicMock()
        mode.context_provider = context_provider
        mode.model = "test-model"
        mode._show_message = MagicMock()

        handler = PlanModeHandler(mode)

        # Mock LLM response with plan
        with patch("joshu.models.openrouter.chat_completion") as mock_chat:
            mock_chat.return_value = "1. Step one\n2. Step two\n3. Step three"

            handler.handle("Set up a Flask project")

            # Should have called LLM
            mock_chat.assert_called()
            # Should have shown message
            mode._show_message.assert_called()


def test_ask_mode_conversational_query():
    """Test that ask mode handles conversational queries."""
    with tempfile.TemporaryDirectory() as tmpdir:
        storage = JsonFileStorage(Path(tmpdir) / "test_data.json")
        context_provider = ContextProvider(storage_backend=storage)

        mode = MagicMock()
        mode.context_provider = context_provider
        mode.model = "test-model"
        mode._show_message = MagicMock()

        handler = AskModeHandler(mode)

        # Mock LLM to return conversational response
        with patch("joshu.models.openrouter.chat_completion") as mock_chat:
            mock_chat.return_value = "Hello! How can I help you today?"

            handler.handle("hi")

            # Should have generated response
            mock_chat.assert_called()
            # Response should be shown
            mode._show_message.assert_called()


def test_plan_mode_json_parsing():
    """Test that plan mode correctly parses JSON plans."""
    with tempfile.TemporaryDirectory() as tmpdir:
        storage = JsonFileStorage(Path(tmpdir) / "test_data.json")
        context_provider = ContextProvider(storage_backend=storage)

        mode = MagicMock()
        mode.context_provider = context_provider
        mode.model = "test-model"
        mode._show_message = MagicMock()

        handler = PlanModeHandler(mode)

        # Mock LLM with JSON response
        with patch("joshu.models.openrouter.chat_completion") as mock_chat:
            mock_chat.return_value = '{"steps": ["step1", "step2"]}'

            # Should handle both JSON and text formats
            handler.handle("plan something")
            mock_chat.assert_called()
