"""Parsing utilities for JSON and command extraction."""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, Optional, Tuple

logger = logging.getLogger(__name__)


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

