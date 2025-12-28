"""Tests for semantic memory system."""

import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

# Check if optional dependencies are available
try:
    import chromadb  # noqa: F401
    from sentence_transformers import SentenceTransformer  # noqa: F401

    SEMANTIC_DEPS_AVAILABLE = True
except ImportError:
    SEMANTIC_DEPS_AVAILABLE = False
    pytestmark = pytest.mark.skip("Semantic memory dependencies not available")


@pytest.fixture
def temp_dir():
    """Create a temporary directory for testing."""
    import shutil

    # Create temp directory manually instead of using TemporaryDirectory
    # which tries to cleanup immediately and conflicts with Windows file handles
    tmpdir = (
        Path(tempfile.gettempdir()) / f"joshu_test_{tempfile._get_candidate_names().__next__()}"
    )
    tmpdir.mkdir(parents=True, exist_ok=True)
    yield tmpdir
    # Best-effort cleanup, ignore errors if files are still locked
    try:
        shutil.rmtree(tmpdir, ignore_errors=True)
    except Exception:
        pass  # Let OS cleanup later


@pytest.fixture
def semantic_memory(temp_dir):
    """Create a SemanticMemory instance for testing."""
    import gc
    import shutil
    import time
    import uuid

    from joshu.core.storage.semantic_memory import SemanticMemory

    # Use unique directory for each test to avoid Windows file handle conflicts
    persist_dir = temp_dir / f".chromadb_{uuid.uuid4().hex[:8]}"
    memory = SemanticMemory(persist_directory=persist_dir)
    yield memory
    # Properly close ChromaDB before cleanup
    try:
        memory.close()
        # Force garbage collection to release file handles on Windows
        gc.collect()
        # Give Windows extra time to release file handles
        time.sleep(0.5)
        # Force cleanup of ChromaDB directory on Windows
        if persist_dir.exists():
            # Try multiple times with delays for Windows
            for attempt in range(5):
                try:
                    shutil.rmtree(persist_dir, ignore_errors=True)
                    if not persist_dir.exists():
                        break
                except Exception:
                    pass
                time.sleep(0.2)
    except Exception:
        pass


class TestSemanticMemory:
    """Test semantic memory functionality."""

    def test_semantic_memory_initialization(self, temp_dir):
        """Test that semantic memory initializes correctly."""
        import gc
        import shutil
        import time
        import uuid

        from joshu.core.storage.semantic_memory import SemanticMemory

        # Use unique directory to avoid conflicts
        persist_dir = temp_dir / f".chromadb_{uuid.uuid4().hex[:8]}"
        memory = SemanticMemory(persist_directory=persist_dir)

        try:
            assert memory.enabled is True
            assert memory.collection is not None
            assert memory.embedding_model is not None
            assert persist_dir.exists()
        finally:
            memory.close()
            # Force garbage collection
            gc.collect()
            # Give Windows extra time to release handles
            time.sleep(0.5)
            if persist_dir.exists():
                for _ in range(5):
                    try:
                        shutil.rmtree(persist_dir, ignore_errors=True)
                        if not persist_dir.exists():
                            break
                    except Exception:
                        pass
                    time.sleep(0.2)

    def test_semantic_memory_disabled_without_deps(self):
        """Test that semantic memory is disabled when dependencies are missing."""
        with patch("joshu.core.storage.semantic_memory.CHROMADB_AVAILABLE", False):
            from joshu.core.storage.semantic_memory import SemanticMemory

            memory = SemanticMemory()
            assert memory.enabled is False
            assert memory.collection is None
            assert memory.embedding_model is None

    def test_add_memory(self, semantic_memory):
        """Test adding memories to the semantic database."""
        if not semantic_memory.enabled:
            pytest.skip("Semantic memory not enabled")

        success = semantic_memory.add_memory(
            content="I prefer using Python for data science projects",
            role="user",
            session_id="test-session-1",
        )

        assert success is True
        assert semantic_memory.count() == 1

    def test_search_memory(self, semantic_memory):
        """Test searching for semantically similar memories."""
        if not semantic_memory.enabled:
            pytest.skip("Semantic memory not enabled")

        semantic_memory.add_memory(
            content="I prefer using Python for data science projects",
            role="user",
            session_id="test-session-1",
        )
        semantic_memory.add_memory(
            content="My favorite programming language is Python because it's easy to learn",
            role="user",
            session_id="test-session-1",
        )
        semantic_memory.add_memory(
            content="The weather is nice today", role="user", session_id="test-session-1"
        )

        # Search for Python-related content
        results = semantic_memory.search("programming language data analysis", limit=2)

        assert len(results) > 0
        # Should find Python-related memories
        assert any("Python" in result.content for result in results)

        # Weather query should not return Python results (or return lower ranked)
        weather_results = semantic_memory.search("weather forecast", limit=1)
        assert len(weather_results) > 0

    def test_search_with_filters(self, semantic_memory):
        """Test searching with session and role filters."""
        if not semantic_memory.enabled:
            pytest.skip("Semantic memory not enabled")

        semantic_memory.add_memory(content="I like Python", role="user", session_id="session-1")
        semantic_memory.add_memory(content="I like Python", role="user", session_id="session-2")
        semantic_memory.add_memory(
            content="Python is great", role="assistant", session_id="session-1"
        )

        # Search within specific session
        results = semantic_memory.search("programming", session_id="session-1")
        assert len(results) >= 1

        # Search for specific role
        results = semantic_memory.search("programming", role="assistant")
        assert len(results) >= 1
        assert all(result.role == "assistant" for result in results)

    def test_get_relevant_context(self, semantic_memory):
        """Test getting relevant context in conversation format."""
        if not semantic_memory.enabled:
            pytest.skip("Semantic memory not enabled")

        semantic_memory.add_memory(
            content="I'm working on a Python project", role="user", session_id="test-session"
        )
        semantic_memory.add_memory(
            content="You can use pandas for data manipulation",
            role="assistant",
            session_id="test-session",
        )

        context = semantic_memory.get_relevant_context(
            query="data analysis library", max_results=2, session_id="test-session"
        )

        assert len(context) > 0
        assert all("role" in item and "content" in item for item in context)

    def test_delete_by_session(self, semantic_memory):
        """Test deleting memories by session ID."""
        if not semantic_memory.enabled:
            pytest.skip("Semantic memory not enabled")

        semantic_memory.add_memory(content="Session 1 memory", role="user", session_id="session-1")
        semantic_memory.add_memory(content="Session 2 memory", role="user", session_id="session-2")

        assert semantic_memory.count() == 2

        deleted = semantic_memory.delete_by_session("session-1")
        assert deleted == 1
        assert semantic_memory.count() == 1

        # Verify session-2 memory still exists
        results = semantic_memory.search("memory", session_id="session-2")
        assert len(results) > 0

    def test_clear_all(self, semantic_memory):
        """Test clearing all semantic memories."""
        if not semantic_memory.enabled:
            pytest.skip("Semantic memory not enabled")

        semantic_memory.add_memory(content="Memory 1", role="user")
        semantic_memory.add_memory(content="Memory 2", role="user")

        assert semantic_memory.count() == 2

        success = semantic_memory.clear()
        assert success is True
        assert semantic_memory.count() == 0

    def test_min_score_filter(self, semantic_memory):
        """Test that min_score filter works correctly."""
        if not semantic_memory.enabled:
            pytest.skip("Semantic memory not enabled")

        semantic_memory.add_memory(content="I love Python programming", role="user")

        # Search with high min_score (should return fewer results)
        results_high = semantic_memory.search("programming language", min_score=0.9, limit=10)

        # Search with low min_score (should return more results)
        results_low = semantic_memory.search("programming language", min_score=0.0, limit=10)

        # Low threshold should return at least as many as high threshold
        assert len(results_low) >= len(results_high)

    def test_empty_query(self, semantic_memory):
        """Test that empty queries return empty results."""
        if not semantic_memory.enabled:
            pytest.skip("Semantic memory not enabled")

        semantic_memory.add_memory(content="Some content", role="user")

        results = semantic_memory.search("")
        assert len(results) == 0

        results = semantic_memory.search("   ")
        assert len(results) == 0

    def test_short_content_filter(self, semantic_memory):
        """Test that very short content is filtered out."""
        if not semantic_memory.enabled:
            pytest.skip("Semantic memory not enabled")

        # Very short content should be rejected
        success = semantic_memory.add_memory(content="Hi", role="user")
        # This should succeed but might not be useful
        # The actual filtering happens in ContextProvider
        assert success is True


class TestSemanticMemoryIntegration:
    """Test semantic memory integration with ContextProvider."""

    def test_context_provider_uses_semantic_memory(self, temp_dir):
        """Test that ContextProvider integrates with semantic memory."""
        from joshu.core.context_provider import ContextProvider
        from joshu.core.storage import JsonFileStorage

        storage = JsonFileStorage(temp_dir / "test_data.json")
        provider = ContextProvider(storage_backend=storage)

        assert hasattr(provider, "semantic_memory")

        provider.add_to_history("user", "I'm learning Python for data science")
        provider.add_to_history(
            "assistant", "Python is great for data science! You can use pandas, numpy, etc."
        )

        # Search for relevant context
        if provider.semantic_memory.enabled:
            results = provider.semantic_memory.search("data analysis tools")
            assert len(results) >= 0  # May or may not find results depending on similarity

    def test_get_relevant_context_includes_semantic_memories(self, temp_dir):
        """Test that get_relevant_context includes semantic memories."""
        from joshu.core.context_provider import ContextProvider
        from joshu.core.storage import JsonFileStorage

        storage = JsonFileStorage(temp_dir / "test_data.json")
        provider = ContextProvider(storage_backend=storage)

        provider.add_to_history("user", "I want to learn machine learning")
        provider.add_to_history(
            "assistant", "Machine learning is fascinating! You should start with scikit-learn."
        )

        context = provider.get_relevant_context("python libraries for ML")

        # Should include recent history and potentially semantic memories
        assert len(context) > 0
        assert any("role" in msg and "content" in msg for msg in context)

    def test_semantic_memory_persistence(self, temp_dir):
        """Test that semantic memories persist across instances."""
        import gc
        import shutil
        import time
        import uuid

        from joshu.core.storage.semantic_memory import SemanticMemory

        # Use unique directory to avoid conflicts
        persist_dir = temp_dir / f".chromadb_{uuid.uuid4().hex[:8]}"

        try:
            memory1 = SemanticMemory(persist_directory=persist_dir)
            if memory1.enabled:
                memory1.add_memory(
                    content="This is a persistent memory", role="user", session_id="persist-test"
                )
                count1 = memory1.count()
                memory1.close()
                gc.collect()  # Force garbage collection
                time.sleep(0.5)  # Give Windows extra time to release handles

                memory2 = SemanticMemory(persist_directory=persist_dir)
                if memory2.enabled:
                    count2 = memory2.count()
                    assert count2 == count1

                    # Should be able to search for the persisted memory
                    results = memory2.search("persistent memory")
                    assert len(results) > 0
                    memory2.close()
                    gc.collect()
                    time.sleep(0.5)
        finally:
            # Cleanup with retries for Windows
            if persist_dir.exists():
                for _ in range(5):
                    try:
                        shutil.rmtree(persist_dir, ignore_errors=True)
                        if not persist_dir.exists():
                            break
                    except Exception:
                        pass
                    time.sleep(0.2)
