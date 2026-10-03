"""Tests for ContextProvider storage integration."""

import tempfile
from pathlib import Path

from joshu.core.context_provider import ContextProvider
from joshu.core.storage import JsonFileStorage


def test_context_provider_initialization_with_storage():
    """Test that ContextProvider initializes correctly with storage backend."""
    with tempfile.TemporaryDirectory() as tmpdir:
        storage = JsonFileStorage(Path(tmpdir) / "test_data.json")
        provider = ContextProvider(storage_backend=storage)
        assert provider.max_history == 100
        assert provider.max_memory_entries == 1000
        assert len(provider.conversation_context.messages) == 0
        assert len(provider.memory_store.kv) == 0


def test_context_provider_clear_context_with_storage():
    """Test clearing all context with storage backend."""
    with tempfile.TemporaryDirectory() as tmpdir:
        storage = JsonFileStorage(Path(tmpdir) / "test_data.json")
        provider = ContextProvider(storage_backend=storage)

        provider.add_to_history("user", "Hello")
        provider.set_memory("test_key", "test_value")

        assert len(provider.conversation_context.messages) == 1
        assert len(provider.memory_store.kv) == 1

        provider.clear_context()

        assert len(provider.conversation_context.messages) == 0
        assert len(provider.memory_store.kv) == 0


def test_context_provider_get_context_summary_with_storage():
    """Test getting context summary with storage backend."""
    with tempfile.TemporaryDirectory() as tmpdir:
        storage = JsonFileStorage(Path(tmpdir) / "test_data.json")
        provider = ContextProvider(storage_backend=storage)
        provider.set_system_info("Linux")

        provider.add_to_history("user", "Hello")
        provider.set_memory("test_key", "test_value")

        summary = provider.get_context_summary()

        assert summary["history_length"] == 1
        assert summary["memory_entries"] == 1
        assert summary["system_info"] == "Linux"
        assert len(summary["recent_history"]) == 1


def test_context_provider_update_from_response_with_storage():
    """Test that context provider updates correctly from responses with storage."""
    with tempfile.TemporaryDirectory() as tmpdir:
        storage = JsonFileStorage(Path(tmpdir) / "test_data.json")
        context_provider = ContextProvider(storage_backend=storage)

        # Initial state
        assert len(context_provider.conversation_context.messages) == 0
        assert len(context_provider.memory_store.kv) == 0

        # Update context from response
        context_provider.update_context_from_response("Hello", "Hi there!")

        # Should have added to history
        assert len(context_provider.conversation_context.messages) == 2
        assert context_provider.conversation_context.messages[0]["role"] == "user"
        assert context_provider.conversation_context.messages[0]["content"] == "Hello"
        assert context_provider.conversation_context.messages[1]["role"] == "assistant"
        assert context_provider.conversation_context.messages[1]["content"] == "Hi there!"

        # Should have stored last interaction in memory
        assert context_provider.get_memory("last_user_input") == "Hello"
        assert context_provider.get_memory("last_system_response") == "Hi there!"


def test_context_provider_clear_context_integration():
    """Test that context provider clears correctly with storage."""
    with tempfile.TemporaryDirectory() as tmpdir:
        storage = JsonFileStorage(Path(tmpdir) / "test_data.json")
        context_provider = ContextProvider(storage_backend=storage)

        # Add some data
        context_provider.add_to_history("user", "Hello")
        context_provider.set_memory("test_key", "test_value")

        assert len(context_provider.conversation_context.messages) == 1
        assert len(context_provider.memory_store.kv) == 1

        # Clear context
        context_provider.clear_context()

        assert len(context_provider.conversation_context.messages) == 0
        assert len(context_provider.memory_store.kv) == 0
