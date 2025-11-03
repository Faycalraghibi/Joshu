"""Shared utilities for model providers."""

from __future__ import annotations

import json
import logging
import re
import time
from functools import wraps
from typing import Any, Callable, Dict, Generator, Optional, Tuple, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


def retry_on_failure(
    max_retries: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0,
    exceptions: tuple[type[Exception], ...] = (Exception,),
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """
    Decorator to retry a function on failure.
    
    Args:
        max_retries: Maximum number of retry attempts
        delay: Initial delay between retries in seconds
        backoff: Multiplier for delay after each retry
        exceptions: Tuple of exception types to catch and retry
    
    Returns:
        Decorated function with retry logic
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            current_delay = delay
            last_exception = None
            
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt < max_retries - 1:
                        logger.debug(
                            f"Retry {attempt + 1}/{max_retries} for {func.__name__} "
                            f"after {current_delay}s: {e}"
                        )
                        time.sleep(current_delay)
                        current_delay *= backoff
                    else:
                        logger.warning(
                            f"Max retries ({max_retries}) exceeded for {func.__name__}: {e}"
                        )
            
            if last_exception:
                raise last_exception
            raise RuntimeError(f"Function {func.__name__} failed after {max_retries} retries")
        
        return wrapper
    return decorator


def parse_json_response(response: str) -> Optional[Dict[str, Any]]:
    """
    Parse JSON from a response string, handling markdown code blocks and extra text.
    
    Args:
        response: Response string that may contain JSON
    
    Returns:
        Parsed JSON dictionary or None if parsing fails
    """
    if not response:
        return None
    
    cleaned = response.strip()
    
    # Remove markdown code blocks
    if cleaned.startswith("```json"):
        cleaned = cleaned[7:]
    if cleaned.startswith("```"):
        cleaned = cleaned[3:]
    if cleaned.endswith("```"):
        cleaned = cleaned[:-3]
    
    cleaned = cleaned.strip()
    
    # Try to find JSON object in the response
    first_brace = cleaned.find('{')
    last_brace = cleaned.rfind('}')
    
    if first_brace != -1 and last_brace != -1 and first_brace < last_brace:
        json_str = cleaned[first_brace:last_brace + 1]
        try:
            return json.loads(json_str)
        except json.JSONDecodeError:
            pass
    
    # Try parsing the entire cleaned string
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass
    
    return None


def extract_command_and_explanation(response: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Extract command and explanation from a response string.
    
    Args:
        response: Response string that may contain command and explanation
    
    Returns:
        Tuple of (command, explanation) or (None, None) if extraction fails
    """
    # Try parsing as JSON first
    data = parse_json_response(response)
    if data:
        command = data.get("command", "").strip()
        explanation = data.get("explanation", "").strip()
        if command and explanation:
            return command, explanation
    
    # Try regex patterns for non-JSON responses
    command_match = re.search(r'[Cc]ommand["\']?\s*[:：]?\s*["\']?([^"\n\r]+)', response)
    explanation_match = re.search(
        r'[Ee]xplanation["\']?\s*[:：]?\s*["\']?([^"\n\r]+)', response
    )
    
    command = command_match.group(1).strip() if command_match else None
    explanation = explanation_match.group(1).strip() if explanation_match else None
    
    return command, explanation


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


