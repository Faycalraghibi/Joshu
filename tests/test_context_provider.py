import pytest
from unittest.mock import patch, MagicMock

from joshu.core.context_provider import ContextProvider, ContextEntry


def test_context_provider_initialization():
    """Test that ContextProvider initializes correctly."""
    provider = ContextProvider()
    assert provider.max_history == 100
    assert provider.max_memory_entries == 1000
    assert len(provider.conversation_context.messages) == 0
    assert len(provider.memory_store.kv) == 0


def test_context_provider_add_to_history():
    """Test adding entries to history."""
    provider = ContextProvider()
    
    provider.add_to_history("user", "Hello")
    provider.add_to_history("assistant", "Hi there!")
    
    assert len(provider.conversation_context.messages) == 2
    assert provider.conversation_context.messages[0]["role"] == "user"
    assert provider.conversation_context.messages[0]["content"] == "Hello"
    assert provider.conversation_context.messages[1]["role"] == "assistant"
    assert provider.conversation_context.messages[1]["content"] == "Hi there!"


def test_context_provider_memory_operations():
    """Test memory set and get operations."""
    provider = ContextProvider()
    
    provider.set_memory("test_key", "test_value")
    assert provider.get_memory("test_key") == "test_value"
    assert provider.get_memory("nonexistent_key") is None


def test_context_provider_update_context_from_response():
    """Test updating context from user input and response."""
    provider = ContextProvider()
    
    provider.update_context_from_response("Hello", "Hi there!")
    
    assert len(provider.conversation_context.messages) == 2
    assert provider.get_memory("last_user_input") == "Hello"
    assert provider.get_memory("last_system_response") == "Hi there!"


def test_context_provider_clear_context():
    """Test clearing all context."""
    provider = ContextProvider()
    
    provider.add_to_history("user", "Hello")
    provider.set_memory("test_key", "test_value")
    
    assert len(provider.conversation_context.messages) == 1
    assert len(provider.memory_store.kv) == 1
    
    provider.clear_context()
    
    assert len(provider.conversation_context.messages) == 0
    assert len(provider.memory_store.kv) == 0


def test_context_provider_get_relevant_context():
    """Test getting relevant context."""
    provider = ContextProvider()
    from joshu.tools.system_info import get_detailed_system_info
    provider.set_system_info(get_detailed_system_info())
    
    provider.add_to_history("user", "Hello")
    provider.add_to_history("assistant", "Hi there!")
    provider.set_memory("user_preference", "likes python")
    
    context = provider.get_relevant_context("Show me python files")
    
    # Should include system info, conversation history, and memory
    assert len(context) >= 3
    # Check that system information is included in the context
    assert any("System Information:" in msg.get("content", "") for msg in context)
    assert any("Hello" in msg.get("content", "") for msg in context)
    assert any("user_preference" in msg.get("content", "") for msg in context)


def test_context_provider_get_context_summary():
    """Test getting context summary."""
    provider = ContextProvider()
    provider.set_system_info("Linux")
    
    provider.add_to_history("user", "Hello")
    provider.set_memory("test_key", "test_value")
    
    summary = provider.get_context_summary()
    
    assert summary["history_length"] == 1
    assert summary["memory_entries"] == 1
    assert summary["system_info"] == "Linux"
    assert len(summary["recent_history"]) == 1


def test_context_provider_history_limit():
    """Test that history is limited to max_history."""
    provider = ContextProvider(max_history=3)
    
    # Add more messages than the limit
    for i in range(5):
        provider.add_to_history("user", f"Message {i}")
    
    # Should only keep the most recent messages
    assert len(provider.conversation_context.messages) == 3
    assert provider.conversation_context.messages[0]["content"] == "Message 2"
    assert provider.conversation_context.messages[1]["content"] == "Message 3"
    assert provider.conversation_context.messages[2]["content"] == "Message 4"