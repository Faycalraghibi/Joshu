from __future__ import annotations

import json
import logging
import time
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

# Import project-level system prompt loader
from joshu.tools.memory import load_project_system_prompt

from .context import ConversationContext
from .memory import MemoryStore
from .storage import (
    EntryType,
    JsonFileStorage,
    QueryFilter,
    StorageBackend,
    StorageEntry,
)
from .storage.semantic_memory import SemanticMemory

logger = logging.getLogger(__name__)

# Try to import dependencies for attention mechanism (optional)
try:
    from sentence_transformers import SentenceTransformer
    from sklearn.metrics.pairwise import cosine_similarity

    ATTENTION_AVAILABLE = True
except ImportError:
    ATTENTION_AVAILABLE = False
    logger.debug(
        "Attention mechanism dependencies not available. Install with: pip install -e .[semantic]"
    )


@dataclass
class ContextEntry:
    """Represents a single entry in the context."""

    role: str
    content: str
    timestamp: Optional[float] = None
    metadata: Optional[Dict[str, Any]] = None


class ContextProvider:
    """
    A context provider that manages conversation history and memory,
    and keeps the LLM updated with relevant context.
    """

    def __init__(
        self,
        max_history: int = 100,
        max_memory_entries: int = 1000,
        conversation_log_file: Optional[Path] = None,
        storage_backend: Optional[StorageBackend] = None,
        config: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Initialize the context provider.

        Args:
            max_history: Maximum number of conversation history entries to keep
            max_memory_entries: Maximum number of memory entries to keep
            conversation_log_file: Optional path (deprecated, kept for backward compatibility only)
            storage_backend: Optional storage backend. If None, creates a JsonFileStorage.
        """
        # Initialize storage backend
        if storage_backend is None:
            storage_backend = JsonFileStorage(Path.cwd() / "cache" / "joshu_data.json")
        self.storage = storage_backend

        # conversation_log_file is deprecated - no longer used
        # All data is now stored in JSON format via storage backend
        # Keep a reference for session file location only
        if conversation_log_file is None:
            # Use storage path parent for session files
            storage_path = Path.cwd()
        else:
            storage_path = Path(conversation_log_file).parent
        self._storage_path = storage_path

        self.conversation_context = ConversationContext()
        self.memory_store = MemoryStore(storage_backend=self.storage)

        # Initialize semantic memory (optional - will be disabled if dependencies not available)
        semantic_persist_dir = storage_path / ".joshu_chromadb"
        self.semantic_memory = SemanticMemory(persist_directory=semantic_persist_dir)

        self.max_history = max_history
        self.max_memory_entries = max_memory_entries
        self.system_info: Optional[str] = None

        # Initialize attention mechanism configuration
        self.config = config or {}
        self.attention_enabled = self.config.get("attention_enabled", True)
        self.attention_similarity_weight = self.config.get("attention_similarity_weight", 0.8)
        self.attention_recency_weight = self.config.get("attention_recency_weight", 0.2)
        self.max_context_turns = self.config.get("max_context_turns", 10)

        # Initialize embedding model for attention mechanism if enabled
        self.embedding_model = None
        if self.attention_enabled and ATTENTION_AVAILABLE:
            try:
                # Use a lightweight model for efficiency (all-MiniLM-L6-v2)
                self.embedding_model = SentenceTransformer("all-MiniLM-L6-v2")
                logger.debug("Attention mechanism initialized with sentence-transformers")
            except Exception as e:
                logger.warning(f"Failed to load sentence transformer for attention: {e}")
                self.attention_enabled = False
        elif self.attention_enabled and not ATTENTION_AVAILABLE:
            logger.info(
                "Attention mechanism requested but dependencies not available. Install with: pip install -e .[semantic]"
            )
            self.attention_enabled = False

        # Session ID for grouping related conversations
        # Always create a NEW session when interactive mode starts (don't resume old sessions)
        self.session_id = self._create_new_session_id()

        # Store session metadata
        self.session_metadata = {
            "id": self.session_id,
            "start_time": datetime.now().isoformat(),
            "mode": None,  # Will be set based on interaction mode
        }

        # Track last user message for pairing with assistant response
        self._last_user_message: Optional[Dict[str, Any]] = None
        self._last_user_timestamp: Optional[float] = None

        # Load project-level system prompt (joshu.md)
        self.project_system_prompt: str = load_project_system_prompt()
        if self.project_system_prompt:
            logger.info("Loaded project-level system prompt from joshu.md")

        # Load existing conversation history from storage
        self._load_conversation_history()

    def _load_conversation_history(self) -> None:
        """Load conversation history from storage backend."""
        try:
            filter = QueryFilter(
                entry_type=EntryType.CONVERSATION,
                limit=self.max_history,
                session_id=self.session_id,
            )
            entries = self.storage.query_entries(filter)

            # Convert storage entries to conversation context messages
            for entry in entries:
                self.conversation_context.add(
                    role=entry.data["role"],
                    content=entry.data["content"],
                    timestamp=entry.timestamp,
                    metadata=entry.metadata,
                )

            logger.debug(f"Loaded {len(entries)} conversation entries from storage")
        except Exception as e:
            logger.warning(f"Failed to load conversation history from storage: {e}")

    def _create_new_session_id(self) -> str:
        """
        Create a new session ID (always creates new, doesn't resume old sessions).

        Session IDs help group related conversations together.
        Each time interactive mode starts, a new session is created.

        Returns:
            Session ID string (UUID format)
        """
        new_session_id = str(uuid.uuid4())

        # Load existing sessions to append this new one
        sessions = self._load_all_sessions()

        # Add new session
        sessions[new_session_id] = {
            "id": new_session_id,
            "start_time": datetime.now().isoformat(),
            "end_time": None,
            "active": True,
        }

        # Save all sessions
        self._save_all_sessions(sessions)

        logger.debug(f"Started new session: {new_session_id[:8]}...")
        return new_session_id

    def _get_sessions_file(self) -> Path:
        """Get the path to the sessions metadata file."""
        return self._storage_path / "cache" / "joshu_sessions.json"

    def _load_all_sessions(self) -> Dict[str, Dict[str, Any]]:
        """Load all sessions from the sessions file."""
        sessions_file = self._get_sessions_file()
        if sessions_file.exists():
            try:
                with open(sessions_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.debug(f"Could not load sessions: {e}")
        return {}

    def _save_all_sessions(self, sessions: Dict[str, Dict[str, Any]]) -> None:
        """Save all sessions to the sessions file."""
        sessions_file = self._get_sessions_file()
        try:
            sessions_file.parent.mkdir(parents=True, exist_ok=True)
            with open(sessions_file, "w", encoding="utf-8") as f:
                json.dump(sessions, f, indent=2)
        except Exception as e:
            logger.warning(f"Could not save sessions: {e}")

    def list_sessions(self) -> List[Dict[str, Any]]:
        """
        List all available sessions.

        Returns:
            List of session dictionaries with id, start_time, end_time, active status
        """
        sessions = self._load_all_sessions()
        result = []
        for session_id, metadata in sessions.items():
            result.append(
                {
                    "id": session_id,
                    "short_id": session_id[:8],
                    "start_time": metadata.get("start_time", "Unknown"),
                    "end_time": metadata.get("end_time"),
                    "active": metadata.get("active", False),
                }
            )
        # Sort by start_time, most recent first
        result.sort(key=lambda x: x["start_time"], reverse=True)
        return result

    def delete_session(self, session_id: str) -> bool:
        """
        Delete a session by ID.

        Args:
            session_id: Full session ID or short ID (first 8 characters)

        Returns:
            True if deleted, False if not found
        """
        sessions = self._load_all_sessions()

        # Find session by full ID or short ID
        found_id = None
        for sid in sessions.keys():
            if sid == session_id or sid.startswith(session_id):
                found_id = sid
                break

        if found_id:
            # Mark as deleted (or remove from active list)
            sessions[found_id]["active"] = False
            sessions[found_id]["end_time"] = datetime.now().isoformat()
            self._save_all_sessions(sessions)
            logger.info(f"Deleted session: {found_id[:8]}...")
            return True

        return False

    def switch_session(self, session_id: str) -> bool:
        """
        Switch to an existing session.

        Args:
            session_id: Full session ID or short ID (first 8 characters)

        Returns:
            True if switched, False if not found
        """
        sessions = self._load_all_sessions()

        # Find session by full ID or short ID
        found_id = None
        for sid in sessions.keys():
            if sid == session_id or sid.startswith(session_id):
                found_id = sid
                break

        if found_id and sessions[found_id].get("active", False):
            # Update current session
            old_session_id = self.session_id
            self.session_id = found_id
            self.session_metadata = sessions[found_id].copy()
            logger.info(f"Switched from session {old_session_id[:8]}... to {found_id[:8]}...")
            return True

        return False

    def end_session(self) -> bool:
        """
        End the current session by deleting it from the sessions file.

        Note: Semantic memories are preserved for cross-session recall.
        To clear semantic memories for this session, call semantic_memory.delete_by_session()
        directly if needed.

        Returns:
            True if session was ended successfully, False otherwise
        """
        sessions = self._load_all_sessions()
        if self.session_id in sessions:
            # Delete the session from the sessions dictionary
            del sessions[self.session_id]
            self._save_all_sessions(sessions)
            logger.info(f"Ended and deleted session: {self.session_id[:8]}...")
            return True
        return False

    def new_session(self) -> str:
        """
        Start a new session (generate new session ID).

        Returns:
            New session ID string
        """
        # Mark old session as inactive
        sessions = self._load_all_sessions()
        if self.session_id in sessions:
            sessions[self.session_id]["active"] = False
            sessions[self.session_id]["end_time"] = datetime.now().isoformat()

        # Create new session
        new_session_id = str(uuid.uuid4())
        sessions[new_session_id] = {
            "id": new_session_id,
            "start_time": datetime.now().isoformat(),
            "end_time": None,
            "active": True,
        }

        # Update current session
        self.session_id = new_session_id
        self.session_metadata = sessions[new_session_id].copy()

        # Save all sessions
        self._save_all_sessions(sessions)

        logger.info(f"Started new session: {new_session_id[:8]}...")
        return new_session_id

    def add_to_history(
        self, role: str, content: str, metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Add an entry to the conversation history.

        This is the single source of truth for all conversation history across all modes.
        All modes (agent, ask, plan) should use this method to maintain a unified conversation.

        Args:
            role: The role of the speaker (user, assistant, system)
            content: The content of the message
            metadata: Optional metadata about the entry (e.g., mode, timestamp, command results)
        """
        # Determine timestamp from metadata or use current time
        timestamp = (
            metadata.get("timestamp") if metadata and "timestamp" in metadata else time.time()
        )

        # Add session ID to metadata for context awareness
        if metadata is None:
            metadata = {}
        if "session_id" not in metadata:
            metadata["session_id"] = self.session_id

        # Add to conversation context with metadata
        self.conversation_context.add(role, content, timestamp=timestamp, metadata=metadata)

        # Generate entry ID for use in both storage and semantic memory
        entry_id = str(uuid.uuid4())

        # Save to storage backend
        try:
            entry = StorageEntry(
                id=entry_id,
                type=EntryType.CONVERSATION,
                data={"role": role, "content": content},
                timestamp=timestamp,
                metadata=metadata,
            )
            self.storage.save_entry(entry)
        except Exception as e:
            logger.warning(f"Failed to save conversation entry to storage: {e}")

        # Also store in semantic memory for long-term recall
        # Only store substantial messages (skip very short ones like acknowledgements)
        if self.semantic_memory.enabled and len(content.strip()) > 10:
            try:
                self.semantic_memory.add_memory(
                    content=content,
                    role=role,
                    session_id=self.session_id,
                    entry_id=entry_id,
                    metadata=metadata,
                    timestamp=timestamp,
                )
            except Exception as e:
                logger.debug(f"Failed to add to semantic memory (non-critical): {e}")

        # Trim history if it exceeds max_history (keep most recent messages for memory efficiency)
        if len(self.conversation_context.messages) > self.max_history:
            # Keep the most recent messages, maintaining conversation continuity
            self.conversation_context.messages = self.conversation_context.messages[
                -self.max_history :
            ]

        # Track user messages for pairing with assistant responses
        if role == "user":
            self._last_user_message = {
                "content": content,
                "timestamp": timestamp,
                "metadata": metadata or {},
            }
            self._last_user_timestamp = timestamp
            logger.debug(
                f"Tracked user message for logging: {content[:50]}... (mode: {metadata.get('mode') if metadata else 'N/A'})"
            )
        elif role == "assistant":
            # Clear tracked user message after saving (data already saved to JSON storage above)
            self._last_user_message = None
            self._last_user_timestamp = None

        # Log with mode information for debugging
        mode_info = f" (mode: {metadata.get('mode')})" if metadata and "mode" in metadata else ""
        logger.debug(f"Added to history: {role} - {content[:50]}...{mode_info}")

    def set_memory(self, key: str, value: str) -> None:
        """
        Set a value in the memory store.

        Args:
            key: The key to store the value under
            value: The value to store
        """
        self.memory_store.set(key, value)
        logger.debug(f"Set memory: {key} = {value[:50]}...")

    def get_memory(self, key: str) -> Optional[str]:
        """
        Get a value from the memory store.

        Args:
            key: The key to retrieve

        Returns:
            The value stored under the key, or None if not found
        """
        return self.memory_store.get(key)

    def _calculate_attention_score(
        self, turn_text: str, current_query: str, turn_index: int, total_turns: int
    ) -> float:
        """
        Calculates a relevance score for a single conversation turn based on its
        semantic similarity to the current query and its recency.

        Args:
            turn_text: Text content of the conversation turn
            current_query: Current user query
            turn_index: Index of this turn in the conversation history (0-indexed)
           total_turns: Total number of turns in history

        Returns:
            Relevance score between 0.0 and 1.0
        """
        if not self.embedding_model:
            return 0.0

        # 1. Semantic Similarity Score
        try:
            embeddings = self.embedding_model.encode([turn_text, current_query])
            similarity_score = cosine_similarity([embeddings[0]], [embeddings[1]])[0][0]
        except Exception as e:
            logger.debug(f"Failed to calculate similarity score: {e}")
            similarity_score = 0.0

        # 2. Recency Score (newer is better, normalized to 0-1)
        # A simple linear decay: the oldest turn gets 0, the newest gets 1
        recency_score = (turn_index + 1) / total_turns if total_turns > 0 else 0.0

        # Combine the scores using configured weights
        final_score = (self.attention_similarity_weight * similarity_score) + (
            self.attention_recency_weight * recency_score
        )

        return final_score

    def get_relevant_context(self, query: str, max_tokens: int = 3000) -> List[Dict[str, str]]:
        """
        Get relevant context for a query, including conversation history and memory.

        This is the unified method that provides conversation history across all modes.
        It efficiently manages memory by:
        - Limiting the number of messages returned (most recent)
        - Excluding metadata from LLM context (kept internally)
        - Including relevant memory entries

        Args:
            query: The current query to provide context for
            max_tokens: Maximum number of tokens to include in context (default 3000)

        Returns:
            List of context messages formatted for LLM consumption (role, content only)
        """
        context_messages = []

        # Add project-level system prompt first (highest priority)
        if self.project_system_prompt:
            context_messages.append({"role": "system", "content": self.project_system_prompt})

        # Add system information if available
        if self.system_info:
            context_messages.append(
                {"role": "system", "content": f"System Information: {self.system_info}"}
            )

        # Add recent conversation history with intelligent selection
        history_messages = self.conversation_context.as_list()

        # Use attention mechanism if enabled and history exceeds limit
        if (
            self.attention_enabled
            and self.embedding_model
            and len(history_messages) > self.max_context_turns
        ):
            # Score each turn based on relevance to current query
            scored_turns = []
            for i, turn in enumerate(history_messages):
                # Combine user and assistant text for a complete turn representation
                turn_text = f"{turn.get('role', '')}: {turn.get('content', '')}"
                score = self._calculate_attention_score(turn_text, query, i, len(history_messages))
                scored_turns.append({"turn": turn, "score": score, "index": i})

            # Sort turns by score in descending order
            scored_turns.sort(key=lambda x: x["score"], reverse=True)

            # Re-sort selected turns chronologically to maintain conversation flow
            # We need to preserve the original order using the index
            selected_with_index = [
                (item["turn"], item["index"]) for item in scored_turns[: self.max_context_turns]
            ]
            selected_with_index.sort(key=lambda x: x[1])
            recent_messages = [turn for turn, _ in selected_with_index]

            logger.debug(
                f"Attention mechanism selected {len(recent_messages)} most relevant turns from {len(history_messages)} total"
            )
        else:
            # Fallback to simple truncation if attention is disabled or history is within limit
            max_history_messages = min(
                self.max_context_turns if hasattr(self, "max_context_turns") else 20,
                len(history_messages),
            )
            recent_messages = (
                history_messages[-max_history_messages:]
                if len(history_messages) > max_history_messages
                else history_messages
            )
            logger.debug(f"Using simple truncation: {len(recent_messages)} recent messages")

        # Add session context information
        current_session_id = getattr(self, "session_id", None)
        if current_session_id:
            session_short = current_session_id[:8]
            # Group messages by session for better context understanding
            session_info = f"Current Session: {session_short}...\n"
            context_messages.append({"role": "system", "content": session_info})

        for message in recent_messages:
            # Include session ID in content for LLM to understand context grouping
            msg_content = message["content"]
            msg_metadata = message.get("metadata", {})
            msg_session_id = (
                msg_metadata.get("session_id", "")[:8] if msg_metadata.get("session_id") else ""
            )

            # Only include role and content for LLM context (metadata is for internal use)
            # Optionally add session indicator if different from current session
            if msg_session_id and msg_session_id != (
                current_session_id[:8] if current_session_id else ""
            ):
                msg_content = f"[Session: {msg_session_id}...] {msg_content}"

            context_messages.append({"role": message["role"], "content": msg_content})

        # Add relevant memory entries
        memory_entries = self._get_relevant_memory(query)
        if memory_entries:
            memory_context = "Relevant Memory:\n" + "\n".join(
                [f"{k}: {v}" for k, v in memory_entries.items()]
            )
            context_messages.append({"role": "system", "content": memory_context})

        return context_messages

    def _get_relevant_memory(self, query: str) -> Dict[str, str]:
        """
        Get memory entries relevant to the query.

        Args:
            query: The query to find relevant memory for

        Returns:
            Dictionary of relevant memory entries
        """
        memory_dict = {}

        # First, get traditional key-value memory entries
        for key in self.memory_store.kv:
            memory_dict[key] = self.memory_store.kv[key]

        # Then, add semantically relevant memories from semantic memory
        if self.semantic_memory.enabled:
            try:
                semantic_results = self.semantic_memory.search(
                    query=query,
                    limit=5,
                    session_id=self.session_id,
                    min_score=0.3,  # Only include reasonably relevant results
                )

                # Add semantic memories as entries
                for i, entry in enumerate(semantic_results):
                    memory_dict[f"semantic_memory_{i}"] = f"{entry.role}: {entry.content}"
            except Exception as e:
                logger.debug(f"Failed to get semantic memory (non-critical): {e}")

        return memory_dict

    def update_context_from_response(self, user_input: str, response: str) -> None:
        """
        Update context based on the user input and system response.

        Args:
            user_input: The user's input
            response: The system's response
        """
        # Add user input to history
        self.add_to_history("user", user_input)

        # Add system response to history
        self.add_to_history("assistant", response)

        # Extract and store any facts or preferences from the interaction
        self._extract_and_store_facts(user_input, response)

    def _extract_and_store_facts(self, user_input: str, response: str) -> None:
        """
        Extract facts and preferences from the interaction and store them in memory.

        Args:
            user_input: The user's input
            response: The system's response
        """
        # This is a simplified implementation. In a real system, this would use
        # an LLM to extract facts and preferences from the conversation.

        # Store the last interaction
        self.set_memory("last_user_input", user_input)
        self.set_memory("last_system_response", response)

        # Extract simple patterns (this is a basic example)
        if "prefer" in user_input.lower() or "like" in user_input.lower():
            self.set_memory("user_preference", user_input)

        if "current directory" in user_input.lower() or "pwd" in user_input.lower():
            # This would be updated with actual directory info in a real implementation
            self.set_memory(
                "working_directory_context", "User is working with file system commands"
            )

    def set_system_info(self, system_info: str) -> None:
        """
        Set system information for context.

        Args:
            system_info: Information about the current system
        """
        self.system_info = system_info

    def clear_context(self) -> None:
        """
        Clear all context, including conversation history and memory.

        This method is useful for resetting the conversation state,
        but should be used with caution as it removes all stored context.
        """
        self.conversation_context.clear()
        self.memory_store.clear()
        self.system_info = None

        # Clear semantic memory if enabled
        if self.semantic_memory.enabled:
            try:
                self.semantic_memory.clear()
            except Exception as e:
                logger.warning(f"Failed to clear semantic memory: {e}")

        logger.info("Context cleared")

    def get_context_summary(self) -> Dict[str, Any]:
        """
        Get a summary of the current context.

        Returns:
            Dictionary with context summary information
        """
        return {
            "history_length": len(self.conversation_context.messages),
            "memory_entries": len(self.memory_store.kv),
            "system_info": self.system_info,
            "recent_history": (
                self.conversation_context.messages[-5:]
                if self.conversation_context.messages
                else []
            ),
        }

    def generate_memory_summary(self) -> str:
        """
        Generate a human-readable summary of the conversation history and memory.

        Returns:
            String summary of the context
        """
        summary_parts = []

        # Add system information
        if self.system_info:
            summary_parts.append(f"System: {self.system_info}")

        # Add conversation history summary - unified across all modes
        if self.conversation_context.messages:
            summary_parts.append(
                f"Conversation history ({len(self.conversation_context.messages)} interactions across all modes):"
            )
            # Show last 10 interactions for better context
            for msg in self.conversation_context.messages[-10:]:
                mode_info = ""
                if msg.get("metadata") and msg["metadata"].get("mode"):
                    mode_info = f" [{msg['metadata']['mode']}]"
                summary_parts.append(
                    f"  {msg['role'].title()}{mode_info}: {msg['content'][:100]}{'...' if len(msg['content']) > 100 else ''}"
                )
        else:
            summary_parts.append("No conversation history.")

        # Add memory entries
        if self.memory_store.kv:
            summary_parts.append(f"Memory entries ({len(self.memory_store.kv)} items):")
            for key, value in self.memory_store.kv.items():
                summary_parts.append(f"  {key}: {value[:100]}{'...' if len(value) > 100 else ''}")
        else:
            summary_parts.append("No memory entries.")

        return "\n".join(summary_parts)

    def get_full_conversation(self) -> List[Dict[str, Any]]:
        """
        Get the full conversation history across all modes.

        This returns all conversation messages with their metadata, providing
        a complete view of the interaction history regardless of mode.

        Returns:
            List of all conversation messages with metadata
        """
        return list(self.conversation_context.messages)
