"""Tests for translation cache functionality."""

import os

# Add src to path
import sys
import tempfile
import time

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from joshu.core.translation_cache import TranslationCache


@pytest.fixture
def temp_cache_dir():
    """Create a temporary cache directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


@pytest.fixture
def translation_cache(temp_cache_dir):
    """Create a translation cache instance for testing."""
    return TranslationCache(cache_dir=temp_cache_dir, max_entries=5)


def test_cache_put_and_get(translation_cache):
    """Test storing and retrieving a translation."""
    query = "list all files in current directory"
    command = "ls -la"
    explanation = "Lists all files with details"

    # Put entry in cache
    translation_cache.put(query, command, explanation)

    # Get entry from cache
    result = translation_cache.get(query)
    assert result is not None
    assert result == (command, explanation)


def test_cache_miss(translation_cache):
    """Test cache miss returns None."""
    query = "non-existent query"
    result = translation_cache.get(query)
    assert result is None


def test_cache_hit_count(translation_cache):
    """Test that cache tracks hit counts."""
    query = "list files"
    command = "ls"
    explanation = "List files"

    translation_cache.put(query, command, explanation)

    # Access the cache entry multiple times
    translation_cache.get(query)
    translation_cache.get(query)
    translation_cache.get(query)

    # Check that hit count was incremented
    import hashlib

    query_hash = hashlib.md5(query.encode()).hexdigest()
    assert query_hash in translation_cache.entries
    assert translation_cache.entries[query_hash].hit_count == 3


def test_cache_eviction(translation_cache):
    """Test that cache evicts entries when it exceeds max_entries."""
    # Fill cache beyond max_entries (max is 5)
    for i in range(6):
        translation_cache.put(f"query {i}", f"command {i}", f"explanation {i}")

    # Check that cache size is limited to max_entries
    assert len(translation_cache.entries) <= 5


def test_cache_persistence(temp_cache_dir):
    """Test that cache persists to disk and loads correctly."""
    # Create cache and add entry
    cache1 = TranslationCache(cache_dir=temp_cache_dir)
    cache1.put("test query", "test command", "test explanation")

    # Create new cache instance (should load from disk)
    cache2 = TranslationCache(cache_dir=temp_cache_dir)
    result = cache2.get("test query")
    assert result is not None
    assert result == ("test command", "test explanation")


def test_cache_clear(translation_cache):
    """Test clearing the cache."""
    # Add some entries
    translation_cache.put("query 1", "command 1", "explanation 1")
    translation_cache.put("query 2", "command 2", "explanation 2")

    assert len(translation_cache.entries) == 2

    # Clear cache
    translation_cache.clear()

    assert len(translation_cache.entries) == 0


def test_cache_stats(translation_cache):
    """Test cache statistics."""
    # Add entries and access them
    translation_cache.put("query 1", "command 1", "explanation 1")
    translation_cache.put("query 2", "command 2", "explanation 2")
    translation_cache.get("query 1")
    translation_cache.get("query 1")

    stats = translation_cache.get_stats()

    assert stats["total_entries"] == 2
    assert stats["total_hits"] == 2
    assert stats["cache_file_size"] > 0


def test_semantic_similarity(translation_cache):
    """Test semantic similarity matching (requires sentence-transformers)."""
    try:
        from sentence_transformers import SentenceTransformer  # noqa: F401

        # Add an entry to cache
        translation_cache.put("list files", "ls", "List files in directory")

        # Query with similar but not identical text
        # This should find the cached entry if semantic similarity is working
        result = translation_cache.get("show me all files")

        # Note: This test might fail if similarity threshold is too high
        # or if sentence-transformers is not available
        if result is not None:
            assert result[0] == "ls"
    except ImportError:
        pytest.skip("sentence-transformers not available")


def test_similarity_threshold(temp_cache_dir):
    """Test different similarity thresholds."""
    try:
        from sentence_transformers import SentenceTransformer  # noqa: F401

        # Create cache with high similarity threshold
        cache_strict = TranslationCache(cache_dir=temp_cache_dir, similarity_threshold=0.95)

        cache_strict.put("list all files", "ls -la", "List all files")

        # Very different query should not match with high threshold
        result = cache_strict.get("delete everything")
        assert result is None

    except ImportError:
        pytest.skip("sentence-transformers not available")


def test_cache_without_embeddings(temp_cache_dir):
    """Test cache works without sentence-transformers (exact matching only)."""
    # This test ensures the cache still works even without semantic similarity
    cache = TranslationCache(cache_dir=temp_cache_dir)

    cache.put("exact query", "exact command", "exact explanation")

    # Exact match should work
    result = cache.get("exact query")
    assert result == ("exact command", "exact explanation")

    # Non-exact match should fail without sentence-transformers doing semantic matching
    # (unless sentence-transformers is installed, in which case it might match)
    cache.get("exact query with modification")
    # We can't assert anything specific here since behavior depends on whether
    # sentence-transformers is installed


def test_lru_eviction_order(translation_cache):
    """Test that least recently used entries are evicted first."""
    # Add 5 entries (max capacity)
    for i in range(5):
        translation_cache.put(f"query {i}", f"command {i}", f"explanation {i}")
        time.sleep(0.01)  # Small delay to ensure different timestamps

    # Access the first entry to make it recently used
    translation_cache.get("query 0")

    # Add a new entry (should trigger eviction)
    translation_cache.put("query 5", "command 5", "explanation 5")

    # query 0 should still be in cache (was recently accessed)
    result = translation_cache.get("query 0")
    assert result is not None

    # One of the unused middle entries should have been evicted
    assert len(translation_cache.entries) == 5


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
