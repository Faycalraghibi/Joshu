from __future__ import annotations

import json
import logging
import os
import uuid
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
from dataclasses import dataclass, asdict

from .context import ConversationContext
from .memory import MemoryStore
from .storage import StorageBackend, StorageEntry, EntryType, QueryFilter, JsonFileStorage
from ..models.openrouter import chat_completion

logger = logging.getLogger(__name__)


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
    
    def __init__(self, max_history: int = 100, max_memory_entries: int = 1000, 
                 conversation_log_file: Optional[Path] = None,
                 storage_backend: Optional[StorageBackend] = None) -> None:
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
            storage_backend = JsonFileStorage(Path.cwd() / '.joshu_data.json')
        self.storage = storage_backend
        
        self.conversation_context = ConversationContext()
        self.memory_store = MemoryStore(storage_backend=self.storage)
        self.max_history = max_history
        self.max_memory_entries = max_memory_entries
        self.system_info: Optional[str] = None
        
        # conversation_log_file is deprecated - no longer used
        # All data is now stored in JSON format via storage backend
        # Keep a reference for session file location only
        if conversation_log_file is None:
            # Use storage path parent for session files
            storage_path = Path.cwd()
        else:
            storage_path = Path(conversation_log_file).parent
        self._storage_path = storage_path
        
        # Session ID for grouping related conversations
        # Always create a NEW session when interactive mode starts (don't resume old sessions)
        self.session_id = self._create_new_session_id()
        
        # Store session metadata
        self.session_metadata = {
            "id": self.session_id,
            "start_time": datetime.now().isoformat(),
            "mode": None  # Will be set based on interaction mode
        }
        
        # Track last user message for pairing with assistant response
        self._last_user_message: Optional[Dict[str, Any]] = None
        self._last_user_timestamp: Optional[float] = None
        
        # Load existing conversation history from storage
        self._load_conversation_history()
    
    def _load_conversation_history(self) -> None:
        """Load conversation history from storage backend."""
        try:
            filter = QueryFilter(
                entry_type=EntryType.CONVERSATION,
                limit=self.max_history,
                session_id=self.session_id
            )
            entries = self.storage.query_entries(filter)
            
            # Convert storage entries to conversation context messages
            for entry in entries:
                self.conversation_context.add(
                    role=entry.data["role"],
                    content=entry.data["content"],
                    timestamp=entry.timestamp,
                    metadata=entry.metadata
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
            "active": True
        }
        
        # Save all sessions
        self._save_all_sessions(sessions)
        
        logger.debug(f"Started new session: {new_session_id[:8]}...")
        return new_session_id
    
    def _get_sessions_file(self) -> Path:
        """Get the path to the sessions metadata file."""
        return self._storage_path / '.joshu_sessions.json'
    
    def _load_all_sessions(self) -> Dict[str, Dict[str, Any]]:
        """Load all sessions from the sessions file."""
        sessions_file = self._get_sessions_file()
        if sessions_file.exists():
            try:
                with open(sessions_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.debug(f"Could not load sessions: {e}")
        return {}
    
    def _save_all_sessions(self, sessions: Dict[str, Dict[str, Any]]) -> None:
        """Save all sessions to the sessions file."""
        sessions_file = self._get_sessions_file()
        try:
            with open(sessions_file, 'w', encoding='utf-8') as f:
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
            result.append({
                "id": session_id,
                "short_id": session_id[:8],
                "start_time": metadata.get("start_time", "Unknown"),
                "end_time": metadata.get("end_time"),
                "active": metadata.get("active", False)
            })
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
            "active": True
        }
        
        # Update current session
        self.session_id = new_session_id
        self.session_metadata = sessions[new_session_id].copy()
        
        # Save all sessions
        self._save_all_sessions(sessions)
        
        logger.info(f"Started new session: {new_session_id[:8]}...")
        return new_session_id
        
    def add_to_history(self, role: str, content: str, metadata: Optional[Dict[str, Any]] = None) -> None:
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
        timestamp = metadata.get("timestamp") if metadata and "timestamp" in metadata else time.time()
        
        # Add session ID to metadata for context awareness
        if metadata is None:
            metadata = {}
        if "session_id" not in metadata:
            metadata["session_id"] = self.session_id
        
        # Add to conversation context with metadata
        self.conversation_context.add(role, content, timestamp=timestamp, metadata=metadata)
        
        # Save to storage backend
        try:
            entry = StorageEntry(
                id=str(uuid.uuid4()),
                type=EntryType.CONVERSATION,
                data={
                    "role": role,
                    "content": content
                },
                timestamp=timestamp,
                metadata=metadata
            )
            self.storage.save_entry(entry)
        except Exception as e:
            logger.warning(f"Failed to save conversation entry to storage: {e}")
        
        # Trim history if it exceeds max_history (keep most recent messages for memory efficiency)
        if len(self.conversation_context.messages) > self.max_history:
            # Keep the most recent messages, maintaining conversation continuity
            self.conversation_context.messages = self.conversation_context.messages[-self.max_history:]
        
        # Track user messages for pairing with assistant responses
        if role == "user":
            self._last_user_message = {
                "content": content,
                "timestamp": timestamp,
                "metadata": metadata or {}
            }
            self._last_user_timestamp = timestamp
            logger.debug(f"Tracked user message for logging: {content[:50]}... (mode: {metadata.get('mode') if metadata else 'N/A'})")
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
        
        # Add system information if available
        if self.system_info:
            context_messages.append({
                "role": "system",
                "content": f"System Information: {self.system_info}"
            })
        
        # Add recent conversation history (limit by max_tokens for memory efficiency)
        history_messages = self.conversation_context.as_list()
        # Add the most recent messages in chronological order
        # Limit to recent messages to stay within token budget and maintain efficiency
        # Use more messages if max_tokens allows (default 2000, increase to 20 messages for better context)
        max_history_messages = min(20, len(history_messages))
        recent_messages = history_messages[-max_history_messages:] if len(history_messages) > max_history_messages else history_messages
        
        # Add session context information
        current_session_id = getattr(self, 'session_id', None)
        if current_session_id:
            session_short = current_session_id[:8]
            # Group messages by session for better context understanding
            session_info = f"Current Session: {session_short}...\n"
            context_messages.append({
                "role": "system",
                "content": session_info
            })
        
        for message in recent_messages:
            # Include session ID in content for LLM to understand context grouping
            msg_content = message["content"]
            msg_metadata = message.get("metadata", {})
            msg_session_id = msg_metadata.get("session_id", "")[:8] if msg_metadata.get("session_id") else ""
            
            # Only include role and content for LLM context (metadata is for internal use)
            # Optionally add session indicator if different from current session
            if msg_session_id and msg_session_id != (current_session_id[:8] if current_session_id else ""):
                msg_content = f"[Session: {msg_session_id}...] {msg_content}"
            
            context_messages.append({
                "role": message["role"],
                "content": msg_content
            })
        
        # Add relevant memory entries
        memory_entries = self._get_relevant_memory(query)
        if memory_entries:
            memory_context = "Relevant Memory:\n" + "\n".join(
                [f"{k}: {v}" for k, v in memory_entries.items()]
            )
            context_messages.append({
                "role": "system",
                "content": memory_context
            })
        
        return context_messages
    
    def _get_relevant_memory(self, query: str) -> Dict[str, str]:
        """
        Get memory entries relevant to the query.
        
        Args:
            query: The query to find relevant memory for
            
        Returns:
            Dictionary of relevant memory entries
        """
        # For now, return all memory entries (in a real implementation, 
        # this would use semantic search or other relevance filtering)
        memory_dict = {}
        for key in self.memory_store.kv:
            memory_dict[key] = self.memory_store.kv[key]
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
            self.set_memory("working_directory_context", "User is working with file system commands")
    
    def set_system_info(self, system_info: str) -> None:
        """
        Set system information for context.
        
        Args:
            system_info: Information about the current system
        """
        self.system_info = system_info
    
    def clear_context(self) -> None:
        """Clear all conversation context and memory."""
        self.conversation_context.messages.clear()
        self.memory_store.kv.clear()
        logger.debug("Cleared all context and memory")
    
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
            "recent_history": self.conversation_context.messages[-5:] if self.conversation_context.messages else []
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
            summary_parts.append(f"Conversation history ({len(self.conversation_context.messages)} interactions across all modes):")
            # Show last 10 interactions for better context
            for msg in self.conversation_context.messages[-10:]:
                mode_info = ""
                if msg.get("metadata") and msg["metadata"].get("mode"):
                    mode_info = f" [{msg['metadata']['mode']}]"
                summary_parts.append(f"  {msg['role'].title()}{mode_info}: {msg['content'][:100]}{'...' if len(msg['content']) > 100 else ''}")
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
    