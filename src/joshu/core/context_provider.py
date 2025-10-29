from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional, Union
from dataclasses import dataclass, asdict

from .context import ConversationContext
from .memory import MemoryStore
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
    
    def __init__(self, max_history: int = 100, max_memory_entries: int = 1000) -> None:
        """
        Initialize the context provider.
        
        Args:
            max_history: Maximum number of conversation history entries to keep
            max_memory_entries: Maximum number of memory entries to keep
        """
        self.conversation_context = ConversationContext()
        self.memory_store = MemoryStore()
        self.max_history = max_history
        self.max_memory_entries = max_memory_entries
        self.system_info: Optional[str] = None
        
    def add_to_history(self, role: str, content: str, metadata: Optional[Dict[str, Any]] = None) -> None:
        """
        Add an entry to the conversation history.
        
        Args:
            role: The role of the speaker (user, assistant, system)
            content: The content of the message
            metadata: Optional metadata about the entry
        """
        # Add to conversation context
        self.conversation_context.add(role, content)
        
        # Trim history if it exceeds max_history
        if len(self.conversation_context.messages) > self.max_history:
            # Keep the most recent messages
            self.conversation_context.messages = self.conversation_context.messages[-self.max_history:]
        
        logger.debug(f"Added to history: {role} - {content[:50]}...")
    
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
    
    def get_relevant_context(self, query: str, max_tokens: int = 2000) -> List[Dict[str, str]]:
        """
        Get relevant context for a query, including conversation history and memory.
        
        Args:
            query: The current query to provide context for
            max_tokens: Maximum number of tokens to include in context
            
        Returns:
            List of context messages formatted for LLM consumption
        """
        context_messages = []
        
        # Add system information if available
        if self.system_info:
            context_messages.append({
                "role": "system",
                "content": f"System Information: {self.system_info}"
            })
        
        # Add recent conversation history (limit by max_tokens)
        history_messages = self.conversation_context.as_list()
        # We'll add the most recent messages first, but limit the total
        for message in reversed(history_messages[-10:]):  # Last 10 messages
            context_messages.append(message)
        
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
        
        # Add conversation history summary
        if self.conversation_context.messages:
            summary_parts.append(f"Conversation history ({len(self.conversation_context.messages)} interactions):")
            # Show last 5 interactions
            for msg in self.conversation_context.messages[-5:]:
                summary_parts.append(f"  {msg['role'].title()}: {msg['content'][:100]}{'...' if len(msg['content']) > 100 else ''}")
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