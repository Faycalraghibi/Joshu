"""Tests for interactive ask mode."""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from joshu.core.context_provider import ContextProvider
from joshu.core.llm_client import AssistantTurn, LLMError
from joshu.core.storage import JsonFileStorage
from joshu.ui.interactive.modes import AskModeHandler


class FakeClient:
    model = "fake"

    def __init__(self, answer):
        self.answer = answer
        self.requests = []

    def complete(self, messages, tools=None, **kwargs):
        self.requests.append((messages, tools))
        return AssistantTurn(content=self.answer)


@pytest.fixture
def mode():
    """A mocked InteractiveMode with a real context provider."""
    with tempfile.TemporaryDirectory() as tmpdir:
        storage = JsonFileStorage(Path(tmpdir) / "test_data.json")
        interactive = MagicMock()
        interactive.context_provider = ContextProvider(storage_backend=storage)
        interactive.model = "test-model"
        interactive._show_message = MagicMock()
        yield interactive


def shown(mode):
    return " ".join(str(c.args[0]) for c in mode._show_message.call_args_list)


def test_ask_mode_answers_with_configured_provider(mode):
    client = FakeClient("Python is a programming language.")

    with patch("joshu.core.llm_client.create_chat_client", return_value=client) as create:
        AskModeHandler(mode).handle("What is Python?")

    create.assert_called_once_with("test-model")
    messages, tools = client.requests[0]
    assert tools is None
    assert messages[0]["role"] == "system"
    assert messages[-1] == {"role": "user", "content": "What is Python?"}
    assert "Python is a programming language." in shown(mode)


def test_ask_mode_reuses_client_across_questions(mode):
    client = FakeClient("ok")

    with patch("joshu.core.llm_client.create_chat_client", return_value=client) as create:
        handler = AskModeHandler(mode)
        handler.handle("one")
        handler.handle("two")

    assert create.call_count == 1 and len(client.requests) == 2


def test_ask_mode_reports_missing_provider(mode):
    error = LLMError("Provider 'openrouter' needs an API key: set OPENROUTER_API_KEY.")

    with patch("joshu.core.llm_client.create_chat_client", side_effect=error):
        assert AskModeHandler(mode).handle("hi") is True

    assert "OPENROUTER_API_KEY" in shown(mode)
