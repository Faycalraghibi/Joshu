"""
Intelligent translation cache with semantic similarity matching.

This module provides caching for translation results to reduce redundant API calls
and improve performance. Uses sentence embeddings to match semantically similar queries.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import time
from dataclasses import asdict, dataclass
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Try to import sentence-transformers (optional dependency)
try:
    from sentence_transformers import SentenceTransformer

    SENTENCE_TRANSFORMERS_AVAILABLE = True
except ImportError:
    SENTENCE_TRANSFORMERS_AVAILABLE = False
    logger.debug(
        "sentence-transformers not available. Translation cache will use exact matching only."
    )


@dataclass
class CacheEntry:
    """Represents a cached translation entry."""

    original_query: str
    translated_command: str
    explanation: str
    timestamp: float
    embedding: List[float]
    hit_count: int = 0
    last_hit: float = 0.0


class TranslationCache:
    """Intelligent cache for translation results with semantic similarity matching."""

    def __init__(
        self,
        cache_dir: Optional[str] = None,
        similarity_threshold: float = 0.85,
        max_entries: int = 1000,
    ):
        """
        Initialize the translation cache.

        Args:
            cache_dir: Directory to store cache file. Defaults to ~/.joshu/cache
            similarity_threshold: Minimum similarity score for semantic matches (0.0-1.0)
            max_entries: Maximum number of entries before eviction occurs
        """
        if cache_dir is None:
            cache_dir = os.path.expanduser("~/.joshu/cache")

        self.cache_dir = cache_dir
        self.cache_file = os.path.join(self.cache_dir, "translation_cache.json")
        self.similarity_threshold = similarity_threshold
        self.max_entries = max_entries
        self.entries: Dict[str, CacheEntry] = {}

        # Initialize sentence transformer for embeddings if available
        self.embedding_model = None
        if SENTENCE_TRANSFORMERS_AVAILABLE:
            try:
                self.embedding_model = SentenceTransformer("all-MiniLM-L6-v2")
                logger.debug("Initialized sentence transformer for translation cache")
            except Exception as e:
                logger.warning(f"Failed to initialize sentence transformer: {e}")
                self.embedding_model = None

        # Create cache directory if it doesn't exist
        os.makedirs(self.cache_dir, exist_ok=True)

        # Load existing cache
        self.load_cache()

    def _generate_query_hash(self, query: str) -> str:
        """Generate a hash for the query string."""
        return hashlib.md5(query.encode()).hexdigest()

    def _calculate_similarity(self, embedding1: List[float], embedding2: List[float]) -> float:
        """
        Calculate cosine similarity between two embeddings.

        Args:
            embedding1: First embedding vector
            embedding2: Second embedding vector

        Returns:
            Similarity score between 0.0 and 1.0
        """
        if not SENTENCE_TRANSFORMERS_AVAILABLE:
            return 0.0

        try:
            import numpy as np
            from sklearn.metrics.pairwise import cosine_similarity

            e1 = np.array(embedding1).reshape(1, -1)
            e2 = np.array(embedding2).reshape(1, -1)
            return float(cosine_similarity(e1, e2)[0][0])
        except Exception as e:
            logger.warning(f"Failed to calculate similarity: {e}")
            return 0.0

    def get(self, query: str) -> Optional[Tuple[str, str]]:
        """
        Get a cached translation for the given query.

        Uses exact hash matching first, then falls back to semantic similarity
        matching if sentence-transformers is available.

        Args:
            query: Natural language query

        Returns:
            Tuple of (command, explanation) if found, None otherwise
        """
        query_hash = self._generate_query_hash(query)

        # Check for exact match first
        if query_hash in self.entries:
            entry = self.entries[query_hash]
            entry.hit_count += 1
            entry.last_hit = time.time()
            self.save_cache()
            logger.debug(f"Cache hit (exact match): {query}")
            return (entry.translated_command, entry.explanation)

        # Check for semantic similarity if embeddings are available
        if self.embedding_model is not None and SENTENCE_TRANSFORMERS_AVAILABLE:
            try:
                query_embedding = self.embedding_model.encode(query).tolist()

                best_match = None
                best_similarity = 0.0

                for entry_hash, entry in self.entries.items():
                    similarity = self._calculate_similarity(query_embedding, entry.embedding)

                    if similarity > best_similarity and similarity >= self.similarity_threshold:
                        best_similarity = similarity
                        best_match = entry

                if best_match:
                    best_match.hit_count += 1
                    best_match.last_hit = time.time()
                    self.save_cache()
                    logger.debug(
                        f"Cache hit (semantic match, similarity={best_similarity:.2f}): {query}"
                    )
                    return (best_match.translated_command, best_match.explanation)
            except Exception as e:
                logger.warning(f"Semantic similarity search failed: {e}")

        logger.debug(f"Cache miss: {query}")
        return None

    def put(self, query: str, command: str, explanation: str) -> None:
        """
        Store a translation in the cache.

        Args:
            query: The original natural language query
            command: The translated shell command
            explanation: Explanation of the command
        """
        query_hash = self._generate_query_hash(query)

        # Generate embedding for the query if embeddings are available
        embedding = []
        if self.embedding_model is not None and SENTENCE_TRANSFORMERS_AVAILABLE:
            try:
                embedding = self.embedding_model.encode(query).tolist()
            except Exception as e:
                logger.warning(f"Failed to generate embedding: {e}")

        # Create cache entry
        entry = CacheEntry(
            original_query=query,
            translated_command=command,
            explanation=explanation,
            timestamp=time.time(),
            embedding=embedding,
            hit_count=0,
            last_hit=0.0,
        )

        # Add to cache
        self.entries[query_hash] = entry
        logger.debug(f"Cached translation: {query}")

        # Evict old entries if cache is full
        if len(self.entries) > self.max_entries:
            self._evict_entries()

        # Save cache
        self.save_cache()

    def _evict_entries(self) -> None:
        """Evict least recently used entries when cache is full."""
        # Sort entries by a combination of recency and frequency
        # Entries with low hit count and old last_hit time are evicted first
        sorted_entries = sorted(
            self.entries.items(),
            key=lambda x: (x[1].last_hit if x[1].last_hit > 0 else x[1].timestamp, x[1].hit_count),
        )

        # Remove oldest entries
        entries_to_remove = len(self.entries) - self.max_entries
        for i in range(entries_to_remove):
            entry_hash = sorted_entries[i][0]
            logger.debug(f"Evicting cache entry: {self.entries[entry_hash].original_query}")
            del self.entries[entry_hash]

    def load_cache(self) -> None:
        """Load cache from disk."""
        if os.path.exists(self.cache_file):
            try:
                with open(self.cache_file, "r", encoding="utf-8") as f:
                    data = json.load(f)

                for entry_hash, entry_data in data.items():
                    self.entries[entry_hash] = CacheEntry(**entry_data)

                logger.debug(f"Loaded {len(self.entries)} cache entries from disk")
            except (json.JSONDecodeError, TypeError) as e:
                logger.warning(f"Error loading cache: {e}")
                self.entries = {}

    def save_cache(self) -> None:
        """Save cache to disk."""
        try:
            # Convert entries to serializable format
            serializable_entries = {
                entry_hash: asdict(entry) for entry_hash, entry in self.entries.items()
            }

            with open(self.cache_file, "w", encoding="utf-8") as f:
                json.dump(serializable_entries, f, indent=2)

            logger.debug(f"Saved {len(self.entries)} cache entries to disk")
        except (TypeError, IOError) as e:
            logger.warning(f"Error saving cache: {e}")

    def clear(self) -> None:
        """Clear all cache entries."""
        self.entries = {}
        if os.path.exists(self.cache_file):
            try:
                os.remove(self.cache_file)
                logger.info("Cache cleared successfully")
            except OSError as e:
                logger.warning(f"Error removing cache file: {e}")

    def get_stats(self) -> Dict:
        """
        Get cache statistics.

        Returns:
            Dictionary with cache statistics:
            - total_entries: Number of cached entries
            - total_hits: Total number of cache hits
            - cache_file_size: Size of cache file in bytes
        """
        total_entries = len(self.entries)
        total_hits = sum(entry.hit_count for entry in self.entries.values())
        cache_file_size = 0

        if os.path.exists(self.cache_file):
            try:
                cache_file_size = os.path.getsize(self.cache_file)
            except OSError:
                pass

        return {
            "total_entries": total_entries,
            "total_hits": total_hits,
            "cache_file_size": cache_file_size,
        }
