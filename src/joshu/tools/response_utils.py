"""Response processing and formatting utilities."""

from __future__ import annotations

from typing import Any, Dict, Generator, Optional


def is_conversational_response(response: str, explanation: Optional[str] = None) -> bool:
    """
    Determine if a response appears to be conversational rather than a command.
    
    Args:
        response: Response text to analyze
        explanation: Optional explanation text to analyze
    
    Returns:
        True if response appears conversational, False otherwise
    """
    # Check explanation for conversational keywords
    if explanation:
        explanation_lower = explanation.lower()
        conversational_keywords = [
            "conversational response",
            "direct response",
            "direct answer",
            "to user's query",
            "to user's question",
            "answering",
            "providing answer",
            "providing response",
        ]
        if any(keyword in explanation_lower for keyword in conversational_keywords):
            return True
    
    # Check response format - long echo commands with triple quotes are conversational
    response_normalized = response.replace('\\"', '"').replace("\\'", "'")
    if '"""' in response_normalized:
        return True
    
    # Long echo commands are often conversational
    if response_normalized.startswith('echo "') and len(response) > 100:
        return True
    
    return False


def format_messages_as_prompt(messages: list[Dict[str, str]]) -> str:
    """
    Convert a list of chat messages to a prompt string.
    
    Args:
        messages: List of message dicts with 'role' and 'content' keys
    
    Returns:
        Formatted prompt string
    """
    prompt_parts = []
    for msg in messages:
        role = msg.get("role", "user")
        content = msg.get("content", "")
        if role == "system":
            prompt_parts.append(f"System: {content}\n")
        elif role == "user":
            prompt_parts.append(f"User: {content}\n")
        elif role == "assistant":
            prompt_parts.append(f"Assistant: {content}\n")
    
    prompt = "".join(prompt_parts) + "\nAssistant:"
    return prompt


def chunk_response(response: str, chunk_size: int = 50) -> Generator[str, None, None]:
    """
    Split a response into chunks for streaming.
    
    Args:
        response: Full response text
        chunk_size: Size of each chunk in characters
    
    Yields:
        Chunks of the response
    """
    for i in range(0, len(response), chunk_size):
        yield response[i:i + chunk_size]


