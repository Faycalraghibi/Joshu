"""
Auto-fix module for analyzing command failures and generating fixes.

This module provides functionality to automatically analyze command errors
and generate corrected versions using LLM-based error analysis.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any, Dict, Optional

from joshu.core.context_provider import ContextProvider
from joshu.models.openrouter import chat_completion

logger = logging.getLogger(__name__)


@dataclass
class FixedCommand:
    """Represents a fixed command with explanation."""

    command: str
    explanation: str
    confidence: float = 0.0  # 0.0 to 1.0


def analyze_error_and_generate_fix(
    failed_command: str,
    error_output: str,
    exit_code: int,
    context_provider: Optional[ContextProvider] = None,
    model: str = "meta-llama/llama-3.1-8b-instruct:free",
) -> Optional[FixedCommand]:
    """
    Analyze command failure and generate a fixed version.

    Args:
        failed_command: The command that failed
        error_output: stderr from the failed command
        exit_code: Exit code from the failed command
        context_provider: Optional context provider for conversation history
        model: LLM model to use for fix generation

    Returns:
        FixedCommand with corrected command and explanation, or None if fix cannot be generated
    """
    # Build the prompt for error analysis
    prompt = _build_fix_prompt(failed_command, error_output, exit_code)

    # Get context if available
    context_messages = []
    if context_provider:
        context_messages = context_provider.get_relevant_context(
            query=f"Fix command error: {failed_command}", max_tokens=2000
        )

    # Prepare messages for LLM
    messages = context_messages + [{"role": "user", "content": prompt}]

    try:
        # Call LLM to generate fix
        response = chat_completion(
            model=model,
            messages=messages,
            max_tokens=500,
            temperature=0.1,  # Lower temperature for more deterministic fixes
        )

        if not response or not response.strip():
            logger.debug("Empty response from LLM for auto-fix")
            return None

        # Parse the response
        fixed_command = _parse_fix_response(response, failed_command)

        if fixed_command:
            logger.info(f"Auto-fix generated: {failed_command} -> {fixed_command.command}")

        return fixed_command

    except Exception as e:
        logger.warning(f"Failed to generate auto-fix: {e}")
        return None


def _build_fix_prompt(failed_command: str, error_output: str, exit_code: int) -> str:
    """Build the prompt for LLM to generate a fix."""
    return f"""The following command failed with an error:

Command: {failed_command}
Exit Code: {exit_code}
Error Output:
{error_output[:500]}

Analyze the error and generate a corrected version of the command that should work.
Respond ONLY with a JSON object containing "command" and "explanation" fields.

Example response format:
{{"command": "ls -la", "explanation": "Fixed typo: changed 'sl' to 'ls'"}}

Important:
- Only suggest safe, simple fixes
- Do not suggest destructive commands
- If unclear, suggest the most likely fix
- Keep the fix minimal - only change what's necessary

JSON response:"""


def _parse_fix_response(response: str, original_command: str) -> Optional[FixedCommand]:
    """
    Parse the LLM response to extract the fixed command.

    Args:
        response: Raw LLM response
        original_command: Original failed command

    Returns:
        FixedCommand if parsing successful, None otherwise
    """
    try:
        # Clean up the response
        cleaned = response.strip()

        # Remove markdown code blocks if present
        if cleaned.startswith("```json"):
            cleaned = cleaned[7:]
        elif cleaned.startswith("```"):
            cleaned = cleaned[3:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        cleaned = cleaned.strip()

        # Try to parse as JSON
        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError:
            # Try to extract JSON from text
            import re

            json_match = re.search(r'\{[^}]*"command"[^}]*"explanation"[^}]*\}', cleaned, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())
            else:
                logger.debug(f"Could not parse fix response as JSON: {cleaned[:100]}")
                return None

        # Extract command and explanation
        if not isinstance(data, dict):
            return None

        command = data.get("command", "").strip()
        explanation = data.get("explanation", "").strip()

        # Validate the fix
        if not command or command == original_command:
            logger.debug("Auto-fix generated same command or empty command")
            return None

        # Calculate confidence based on explanation quality
        confidence = 0.7  # Default confidence
        if len(explanation) > 20:
            confidence = 0.8
        if "fixed" in explanation.lower() or "corrected" in explanation.lower():
            confidence = min(0.9, confidence + 0.1)

        return FixedCommand(command=command, explanation=explanation, confidence=confidence)

    except Exception as e:
        logger.debug(f"Error parsing fix response: {e}")
        return None


def should_attempt_auto_fix(config: Dict[str, Any], attempt: int) -> bool:
    """
    Determine if auto-fix should be attempted.

    Args:
        config: Configuration dictionary
        attempt: Current attempt number (0-indexed)

    Returns:
        True if auto-fix should be attempted, False otherwise
    """
    auto_fix_enabled = config.get("auto_fix_enabled", False)
    max_attempts = config.get("auto_fix_max_attempts", 2)

    if not auto_fix_enabled:
        logger.debug("Auto-fix is disabled")
        return False

    if attempt >= max_attempts:
        logger.debug(f"Max auto-fix attempts ({max_attempts}) reached")
        return False

    return True
