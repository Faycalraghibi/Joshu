"""Semantic memory system using ChromaDB for long-term conversation recall."""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# Try to import optional dependencies
try:
    import chromadb
    from chromadb.config import Settings
    CHROMADB_AVAILABLE = True
except ImportError:
    CHROMADB_AVAILABLE = False
    logger.debug("ChromaDB not available. Semantic memory will be disabled.")

try:
    from sentence_transformers import SentenceTransformer
    SENTENCE_TRANSFORMERS_AVAILABLE = True
except ImportError:
    SENTENCE_TRANSFORMERS_AVAILABLE = False
    logger.debug("sentence-transformers not available. Semantic memory will be disabled.")


@dataclass
class SemanticMemoryEntry:
    """Represents a semantically searchable memory entry."""
    id: str
    content: str
    role: str
    session_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    timestamp: Optional[float] = None


class SemanticMemory:
    """
    Semantic memory system using ChromaDB for vector storage and sentence-transformers for embeddings.
    
    This allows Joshu to recall relevant past conversations based on semantic similarity,
    not just keyword matching or recency.
    """
    
    def __init__(
        self,
        collection_name: str = "joshu_memories",
        persist_directory: Optional[Path] = None,
        embedding_model: str = "all-MiniLM-L6-v2"
    ) -> None:
        """
        Initialize semantic memory system.
        
        Args:
            collection_name: Name of the ChromaDB collection
            persist_directory: Directory to persist ChromaDB data. If None, uses .joshu_chromadb
            embedding_model: Name of the sentence-transformers model to use
        """
        if not CHROMADB_AVAILABLE or not SENTENCE_TRANSFORMERS_AVAILABLE:
            self._enabled = False
            logger.warning("Semantic memory disabled due to missing dependencies")
            self.client = None
            self.collection = None
            self.embedding_model = None
            return
        
        self._enabled = True
        self.collection_name = collection_name
        
        # Set up persist directory
        if persist_directory is None:
            persist_directory = Path.cwd() / ".joshu_chromadb"
        self.persist_directory = Path(persist_directory)
        self.persist_directory.mkdir(parents=True, exist_ok=True)
        
        # Initialize ChromaDB client (persistent, local mode)
        try:
            self.client = chromadb.PersistentClient(
                path=str(self.persist_directory),
                settings=Settings(
                    anonymized_telemetry=False,
                    allow_reset=True
                )
            )
            
            # Get or create collection
            self.collection = self.client.get_or_create_collection(
                name=collection_name,
                metadata={"description": "Joshu semantic memory for conversation recall"}
            )
            
            logger.info(f"Initialized ChromaDB collection: {collection_name}")
        except Exception as e:
            logger.error(f"Failed to initialize ChromaDB: {e}")
            self._enabled = False
            self.client = None
            self.collection = None
        
        # Load embedding model
        try:
            self.embedding_model = SentenceTransformer(embedding_model)
            logger.info(f"Loaded embedding model: {embedding_model}")
        except Exception as e:
            logger.error(f"Failed to load embedding model: {e}")
            self._enabled = False
            self.embedding_model = None
    
    @property
    def enabled(self) -> bool:
        """Check if semantic memory is enabled."""
        return self._enabled
    
    def add_memory(
        self,
        content: str,
        role: str = "user",
        session_id: Optional[str] = None,
        entry_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        timestamp: Optional[float] = None
    ) -> bool:
        """
        Add a memory entry to the semantic database.
        
        Args:
            content: The content to store
            role: Role of the speaker (user, assistant, system)
            session_id: Optional session ID
            entry_id: Optional entry ID. If None, generates one
            metadata: Optional metadata dictionary
            timestamp: Optional timestamp. If None, uses current time
            
        Returns:
            True if successful, False otherwise
        """
        if not self._enabled:
            logger.debug("Semantic memory disabled, skipping add")
            return False
        
        if not content or not content.strip():
            return False
        
        try:
            import uuid
            
            if entry_id is None:
                entry_id = str(uuid.uuid4())
            
            if timestamp is None:
                timestamp = time.time()
            
            # Prepare metadata
            doc_metadata = {
                "role": role,
                "timestamp": str(timestamp)
            }
            if session_id:
                doc_metadata["session_id"] = session_id
            if metadata:
                doc_metadata.update(metadata)
            
            # Add to collection (ChromaDB will generate embedding automatically if we provide document)
            # We'll use the content directly and let ChromaDB handle embedding via query_embeddings
            # Actually, ChromaDB needs us to provide embeddings or use its default embedder
            # Since we have sentence-transformers, we'll generate embeddings manually for better control
            
            # Generate embedding
            embedding = self.embedding_model.encode(content, convert_to_numpy=True).tolist()
            
            # Add to ChromaDB collection
            self.collection.add(
                ids=[entry_id],
                embeddings=[embedding],
                documents=[content],
                metadatas=[doc_metadata]
            )
            
            logger.debug(f"Added semantic memory entry: {entry_id[:8]}...")
            return True
            
        except Exception as e:
            logger.error(f"Failed to add semantic memory: {e}")
            return False
    
    def search(
        self,
        query: str,
        limit: int = 5,
        session_id: Optional[str] = None,
        role: Optional[str] = None,
        min_score: float = 0.0
    ) -> List[SemanticMemoryEntry]:
        """
        Search for semantically similar memories.
        
        Args:
            query: Query string to search for
            limit: Maximum number of results to return
            session_id: Optional filter by session ID
            role: Optional filter by role (user, assistant, system)
            min_score: Minimum similarity score (0-1)
            
        Returns:
            List of SemanticMemoryEntry objects, sorted by relevance
        """
        if not self._enabled:
            logger.debug("Semantic memory disabled, returning empty results")
            return []
        
        if not query or not query.strip():
            return []
        
        try:
            # Generate query embedding
            query_embedding = self.embedding_model.encode(query, convert_to_numpy=True).tolist()
            
            # Build where clause for filtering
            where_clause = {}
            if session_id:
                where_clause["session_id"] = session_id
            if role:
                where_clause["role"] = role
            
            # Query ChromaDB
            if where_clause:
                results = self.collection.query(
                    query_embeddings=[query_embedding],
                    n_results=limit,
                    where=where_clause
                )
            else:
                results = self.collection.query(
                    query_embeddings=[query_embedding],
                    n_results=limit
                )
            
            # Convert results to SemanticMemoryEntry objects
            entries = []
            if results and results.get("ids") and len(results["ids"][0]) > 0:
                ids = results["ids"][0]
                documents = results["documents"][0]
                metadatas = results["metadatas"][0] if results.get("metadatas") else [{}] * len(ids)
                distances = results["distances"][0] if results.get("distances") else [0.0] * len(ids)
                
                for i, entry_id in enumerate(ids):
                    # Convert distance to similarity score (ChromaDB returns L2 distance, lower is better)
                    # For cosine similarity, we want to convert distance to similarity
                    # If using cosine distance, similarity = 1 - distance
                    # For L2 distance, we'll approximate: similarity ≈ 1 / (1 + distance)
                    similarity = 1.0 / (1.0 + distances[i]) if distances[i] > 0 else 1.0
                    
                    if similarity >= min_score:
                        metadata = metadatas[i] if i < len(metadatas) else {}
                        
                        entry = SemanticMemoryEntry(
                            id=entry_id,
                            content=documents[i] if i < len(documents) else "",
                            role=metadata.get("role", "user"),
                            session_id=metadata.get("session_id"),
                            metadata={k: v for k, v in metadata.items() if k not in ["role", "session_id", "timestamp"]},
                            timestamp=float(metadata.get("timestamp", time.time()))
                        )
                        entries.append(entry)
            
            logger.debug(f"Semantic search found {len(entries)} results for query: {query[:50]}...")
            return entries
            
        except Exception as e:
            logger.error(f"Failed to search semantic memory: {e}")
            return []
    
    def get_relevant_context(
        self,
        query: str,
        max_results: int = 5,
        session_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get relevant conversation context based on semantic similarity.
        
        This is a convenience method that returns context in the format
        expected by the conversation system.
        
        Args:
            query: Query string to find relevant context
            max_results: Maximum number of context entries to return
            session_id: Optional session ID filter
            
        Returns:
            List of context dictionaries with 'role' and 'content' keys
        """
        entries = self.search(query, limit=max_results, session_id=session_id)
        
        return [
            {
                "role": entry.role,
                "content": entry.content,
                "timestamp": entry.timestamp,
                "metadata": entry.metadata or {}
            }
            for entry in entries
        ]
    
    def delete_by_session(self, session_id: str) -> int:
        """
        Delete all memories from a specific session.
        
        Args:
            session_id: Session ID to delete
            
        Returns:
            Number of entries deleted
        """
        if not self._enabled:
            return 0
        
        try:
            # Query for entries with this session_id
            results = self.collection.get(
                where={"session_id": session_id}
            )
            
            if results and results.get("ids"):
                deleted_count = len(results["ids"])
                # Delete by IDs
                self.collection.delete(ids=results["ids"])
                logger.debug(f"Deleted {deleted_count} semantic memories for session: {session_id}")
                return deleted_count
            
            return 0
            
        except Exception as e:
            logger.error(f"Failed to delete semantic memories by session: {e}")
            return 0
    
    def clear(self) -> bool:
        """
        Clear all semantic memories.
        
        Returns:
            True if successful, False otherwise
        """
        if not self._enabled:
            return False
        
        try:
            # Delete the collection and recreate it
            self.client.delete_collection(name=self.collection_name)
            self.collection = self.client.create_collection(
                name=self.collection_name,
                metadata={"description": "Joshu semantic memory for conversation recall"}
            )
            logger.info("Cleared all semantic memories")
            return True
            
        except Exception as e:
            logger.error(f"Failed to clear semantic memories: {e}")
            return False
    
    def count(self) -> int:
        """
        Get the total number of stored memories.
        
        Returns:
            Number of memories stored
        """
        if not self._enabled:
            return 0
        
        try:
            return self.collection.count()
        except Exception as e:
            logger.error(f"Failed to count semantic memories: {e}")
            return 0
    
    def close(self) -> None:
        """Close the semantic memory system and cleanup resources."""
        if not self._enabled:
            return
        
        try:
            # ChromaDB PersistentClient handles cleanup automatically when garbage collected
            # However, we can help by clearing references
            # The client will release file handles when Python's GC runs
            self.collection = None
            self.client = None
            self.embedding_model = None
            logger.debug("Semantic memory system closed")
        except Exception as e:
            logger.debug(f"Error closing semantic memory: {e}")

