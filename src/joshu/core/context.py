from __future__ import annotations

import time
from typing import Any, Dict, List, Optional


class ConversationContext:
    def __init__(self) -> None:
        self.messages: List[Dict[str, Any]] = []

    def add(self, role: str, content: str, timestamp: Optional[float] = None) -> None:
        """
        Add a message to the conversation context.
        
        Args:
            role: The role of the speaker (user, assistant, system)
            content: The content of the message
            timestamp: Optional timestamp for the message
        """
        message: Dict[str, Any] = {
            "role": role,
            "content": content
        }
        if timestamp is not None:
            message["timestamp"] = timestamp
        else:
            message["timestamp"] = time.time()
            
        self.messages.append(message)

    def as_list(self) -> List[Dict[str, Any]]:
        """
        Get the conversation context as a list of messages.
        
        Returns:
            List of message dictionaries
        """
        return list(self.messages)
    
    def clear(self) -> None:
        """Clear all messages from the context."""
        self.messages.clear()
    
    def get_recent_messages(self, count: int = 10) -> List[Dict[str, Any]]:
        """
        Get the most recent messages from the context.
        
        Args:
            count: Number of recent messages to retrieve
            
        Returns:
            List of recent message dictionaries
        """
        return self.messages[-count:] if self.messages else []