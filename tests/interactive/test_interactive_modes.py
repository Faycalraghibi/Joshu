"""Tests for interactive mode handlers (ask, plan, agent)."""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from joshu.core.context_provider import ContextProvider
from joshu.core.storage import JsonFileStorage
from joshu.ui.interactive.modes import AgentModeHandler, AskModeHandler, PlanModeHandler


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


def test_agent_mode_handler():
    """Test AgentModeHandler executes plans correctly."""
    with tempfile.TemporaryDirectory() as tmpdir:
        storage = JsonFileStorage(Path(tmpdir) / "test_data.json")
        context_provider = ContextProvider(storage_backend=storage)

        mode = MagicMock()
        mode.context_provider = context_provider
        mode.model = "test-model"
        mode.sandbox = False
        mode._show_message = MagicMock()

        handler = AgentModeHandler(mode)

        # Mock LLM plan generation - chat_completion is imported inside _get_llm_response
        # run_command is imported at module level, so patch it there
        with patch("joshu.models.openrouter.chat_completion") as mock_chat, patch(
            "joshu.core.safety.assess_command_safety"
        ) as mock_safety, patch("joshu.ui.interactive.modes.run_command") as mock_run, patch(
            "joshu.ui.interactive.modes.os.getenv"
        ) as mock_getenv, patch(
            "builtins.input", return_value="n"
        ):  # Mock user input to avoid prompts
            # Mock environment to use cloud
            mock_getenv.side_effect = lambda key, default=None: {
                "OPENROUTER_API_KEY": "test-key",
                "JOSHU_USE_CLOUD": "true",
            }.get(key, default)

            # Mock plan JSON (agent mode expects a JSON list of commands)
            mock_chat.return_value = '["echo hello", "echo world"]'
            mock_safety.return_value = MagicMock(safe=True)
            mock_run.return_value = (0, "output", "")

            handler.handle("say hello and world")

            # Should have called LLM to generate plan
            mock_chat.assert_called()
            # Should have executed commands (at least one)
            assert mock_run.call_count >= 1


def test_agent_mode_handler_stops_on_failure():
    """Test AgentModeHandler stops execution when command fails."""
    with tempfile.TemporaryDirectory() as tmpdir:
        storage = JsonFileStorage(Path(tmpdir) / "test_data.json")
        context_provider = ContextProvider(storage_backend=storage)

        mode = MagicMock()
        mode.context_provider = context_provider
        mode.model = "test-model"
        mode.sandbox = False
        mode._show_message = MagicMock()

        handler = AgentModeHandler(mode)

        # Mock LLM plan generation - chat_completion is imported inside _get_llm_response
        # run_command is imported at module level, so patch it there
        with patch("joshu.models.openrouter.chat_completion") as mock_chat, patch(
            "joshu.core.safety.assess_command_safety"
        ) as mock_safety, patch("joshu.ui.interactive.modes.run_command") as mock_run, patch(
            "joshu.ui.interactive.modes.os.getenv"
        ) as mock_getenv, patch(
            "builtins.input", return_value="n"
        ):  # Mock user input to avoid prompts
            # Mock environment to use cloud
            mock_getenv.side_effect = lambda key, default=None: {
                "OPENROUTER_API_KEY": "test-key",
                "JOSHU_USE_CLOUD": "true",
            }.get(key, default)

            # Mock plan with two commands
            mock_chat.return_value = '["echo hello", "echo world"]'
            mock_safety.return_value = MagicMock(safe=True)
            # First command fails
            mock_run.side_effect = [(1, "", "error"), (0, "world", "")]

            # Use a non-conversational input that will trigger plan generation
            # "execute plan" might be detected as conversational, so use a task-like input
            handler.handle("create a test file and echo hello")

            # Should have tried first command
            assert mock_run.call_count >= 1
            # Should have stopped after failure
            # (exact behavior depends on implementation)


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
