"""
Example Integration of Tool Calling.

This module demonstrates how to use the tool calling framework in Joshu.
It can be used as a reference for integrating tool calling into other parts of the codebase.
"""

from __future__ import annotations

import logging
from typing import Optional

from joshu.core.tool_calling_helper import chat_with_tools, get_content_from_response
from joshu.models.openrouter import chat_completion

logger = logging.getLogger(__name__)


def conversational_query_with_tools(
    question: str,
    model: str = "openai/gpt-4o-mini",
    temperature: float = 0.7,
    max_tokens: int = 512,
) -> Optional[str]:
    """
    Answer a conversational question with automatic tool calling support.

    This is an example of how to integrate tool calling into conversational responses.
    The LLM will automatically use tools like web search when needed.

    Args:
        question: User's question
        model: Model to use
        temperature: Sampling temperature
        max_tokens: Maximum tokens in response

    Returns:
        Final answer as a string, or None if failed

    Example:
        >>> answer = conversational_query_with_tools("What are the latest Python 3.13 features?")
        >>> print(answer)
        # Answer will include information from web search if needed
    """
    try:
        # Prepare messages
        system_message = """You are Joshu, a helpful AI assistant.
Answer the user's question directly and helpfully.
You have access to tools like web search - use them when you need current information or external knowledge."""

        messages = [
            {"role": "system", "content": system_message},
            {"role": "user", "content": question},
        ]

        # Use chat_with_tools helper for automatic tool calling
        response = chat_with_tools(
            messages=messages,
            chat_completion_func=chat_completion,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            max_iterations=3,
        )

        if not response:
            return None

        # Extract content from response (backward compatible)
        answer = get_content_from_response(response)
        return answer

    except Exception as e:
        logger.error(f"Conversational query with tools failed: {e}", exc_info=True)
        return None


# Example usage
if __name__ == "__main__":
    # Set up logging
    logging.basicConfig(level=logging.INFO)

    # Make sure tools are registered by importing the implementations
    import joshu.tools.implementations  # noqa: F401

    # Example question that might trigger web search
    question = "What are the latest features in Python 3.13?"

    print(f"Question: {question}\n")
    answer = conversational_query_with_tools(question)

    if answer:
        print(f"Answer: {answer}")
    else:
        print("Failed to get answer")
