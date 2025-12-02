"""
Comprehensive tests for the attention mechanism in ContextProvider.
Tests semantic similarity scoring, relevance-based selection, and fallback behavior.
"""

import tempfile
from pathlib import Path

import pytest

from joshu.core.context_provider import ContextProvider
from joshu.core.storage import JsonFileStorage

# Skip tests if sentence-transformers is not available
try:
    from sentence_transformers import SentenceTransformer  # noqa: F401

    ATTENTION_AVAILABLE = True
except ImportError:
    ATTENTION_AVAILABLE = False


@pytest.mark.skipif(not ATTENTION_AVAILABLE, reason="sentence-transformers not available")
def test_attention_mechanism_initialization():
    """Test that attention mechanism initializes correctly with config."""
    with tempfile.TemporaryDirectory() as tmpdir:
        storage = JsonFileStorage(Path(tmpdir) / "test_data.json")
        config = {
            "attention_enabled": True,
            "attention_similarity_weight": 0.7,
            "attention_recency_weight": 0.3,
            "max_context_turns": 5,
        }
        provider = ContextProvider(storage_backend=storage, config=config)

        assert provider.attention_enabled is True
        assert provider.attention_similarity_weight == 0.7
        assert provider.attention_recency_weight == 0.3
        assert provider.max_context_turns == 5
        assert provider.embedding_model is not None


def test_attention_disabled_initialization():
    """Test that provider works with attention disabled."""
    with tempfile.TemporaryDirectory() as tmpdir:
        storage = JsonFileStorage(Path(tmpdir) / "test_data.json")
        config = {"attention_enabled": False}
        provider = ContextProvider(storage_backend=storage, config=config)

        assert provider.attention_enabled is False
        assert provider.embedding_model is None


@pytest.mark.skipif(not ATTENTION_AVAILABLE, reason="sentence-transformers not available")
def test_attention_selects_relevant_turns():
    """Test that attention mechanism selects semantically relevant turns over recent irrelevant ones."""
    with tempfile.TemporaryDirectory() as tmpdir:
        storage = JsonFileStorage(Path(tmpdir) / "test_data.json")
        config = {
            "attention_enabled": True,
            "attention_similarity_weight": 0.9,  # High weight on similarity
            "attention_recency_weight": 0.1,  # Low weight on recency
            "max_context_turns": 2,
        }
        provider = ContextProvider(storage_backend=storage, config=config)

        # Add an old relevant turn about Python
        provider.add_to_history("user", "How do I install pandas in Python?")
        provider.add_to_history(
            "assistant", "Use pip install pandas to install the pandas library."
        )

        # Add several irrelevant recent turns
        provider.add_to_history("user", "What's the capital of France?")
        provider.add_to_history("assistant", "The capital of France is Paris.")
        provider.add_to_history("user", "Tell me a joke")
        provider.add_to_history(
            "assistant", "Why did the chicken cross the road? To get to the other side!"
        )

        # Query about Python - should retrieve the old relevant turn
        current_query = "I need to install numpy for Python"
        relevant_context = provider.get_relevant_context(current_query)

        # Extract content from context
        content_list = [
            msg["content"] for msg in relevant_context if msg["role"] in ["user", "assistant"]
        ]
        " ".join(content_list)

        #  Should include the pandas/Python turn due to semantic similarity
        assert any(
            "pandas" in content.lower() or "python" in content.lower() for content in content_list
        ), f"Expected Python-related content, got: {content_list}"


@pytest.mark.skipif(not ATTENTION_AVAILABLE, reason="sentence-transformers not available")
def test_attention_maintains_chronological_order():
    """Test that selected turns maintain chronological order."""
    with tempfile.TemporaryDirectory() as tmpdir:
        storage = JsonFileStorage(Path(tmpdir) / "test_data.json")
        config = {"attention_enabled": True, "max_context_turns": 3}
        provider = ContextProvider(storage_backend=storage, config=config)

        # Add turns in specific order
        provider.add_to_history("user", "Question 1 about files")
        provider.add_to_history("assistant", "Answer 1")
        provider.add_to_history("user", "Question 2 about weather")
        provider.add_to_history("assistant", "Answer 2")
        provider.add_to_history("user", "Question 3 about files")
        provider.add_to_history("assistant", "Answer 3")

        # Query about files - should select Q1, Q3 but maintain order
        relevant_context = provider.get_relevant_context("Tell me about file management")

        user_messages = [msg for msg in relevant_context if msg["role"] == "user"]

        # Verify chronological order is maintained (Q1 should come before Q3)
        if len(user_messages) >= 2:
            q1_index = next(
                (i for i, msg in enumerate(user_messages) if "Question 1" in msg["content"]), None
            )
            q3_index = next(
                (i for i, msg in enumerate(user_messages) if "Question 3" in msg["content"]), None
            )

            if q1_index is not None and q3_index is not None:
                assert q1_index < q3_index, "Chronological order not maintained"


def test_attention_fallback_when_disabled():
    """Test that simple truncation is used when attention is disabled."""
    with tempfile.TemporaryDirectory() as tmpdir:
        storage = JsonFileStorage(Path(tmpdir) / "test_data.json")
        config = {"attention_enabled": False, "max_context_turns": 2}
        provider = ContextProvider(storage_backend=storage, config=config)

        # Add multiple messages
        for i in range(5):
            provider.add_to_history("user", f"Message {i}")
            provider.add_to_history("assistant", f"Response {i}")

        # Get context
        context = provider.get_relevant_context("any query")
        user_messages = [msg for msg in context if msg["role"] == "user"]

        # Should only get the most recent 2 user messages (simple truncation)
        assert len(user_messages) <= 2
        # Should be the most recent ones
        if len(user_messages) >= 2:
            assert (
                "Message 3" in user_messages[-2]["content"]
                or "Message 4" in user_messages[-1]["content"]
            )


def test_attention_respects_max_context_turns():
    """Test that attention mechanism respects the max_context_turns limit."""
    config = {"attention_enabled": True, "max_context_turns": 3}

    # Mock the embedding model to avoid actual model loading
    with tempfile.TemporaryDirectory() as tmpdir:
        storage = JsonFileStorage(Path(tmpdir) / "test_data.json")
        provider = ContextProvider(storage_backend=storage, config=config)

        # Add many messages
        for i in range(10):
            provider.add_to_history("user", f"Question {i}")
            provider.add_to_history("assistant", f"Answer {i}")

        # Get context
        context = provider.get_relevant_context("test query")
        user_messages = [msg for msg in context if msg["role"] == "user"]

        # Should not exceed max_context_turns
        assert len(user_messages) <= 3


def test_attention_with_no_history():
    """Test that attention mechanism handles empty history gracefully."""
    with tempfile.TemporaryDirectory() as tmpdir:
        storage = JsonFileStorage(Path(tmpdir) / "test_data.json")
        config = {"attention_enabled": True}
        provider = ContextProvider(storage_backend=storage, config=config)

        # Get context with no history
        context = provider.get_relevant_context("test query")

        # Should return without errors
        assert isinstance(context, list)


def test_attention_scoring_calculation():
    """Test that _calculate_attention_score returns valid scores."""
    with tempfile.TemporaryDirectory() as tmpdir:
        storage = JsonFileStorage(Path(tmpdir) / "test_data.json")
        config = {
            "attention_enabled": True,
            "attention_similarity_weight": 0.8,
            "attention_recency_weight": 0.2,
        }
        provider = ContextProvider(storage_backend=storage, config=config)

        if provider.embedding_model:
            # Test scoring
            score = provider._calculate_attention_score(
                "How do I install Python packages?", "I need to install numpy", 0, 5
            )

            # Score should be between 0 and 1
            assert 0.0 <= score <= 1.0

            # More recent turn should have higher recency component
            score_old = provider._calculate_attention_score("test", "query", 0, 10)
            score_new = provider._calculate_attention_score("test", "query", 9, 10)

            # If similarity is the same, newer should have higher score
            assert score_new >= score_old
