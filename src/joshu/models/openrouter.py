from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

from openai import OpenAI

from .config import ModelConfig
from joshu.tools.parsing_utils import parse_json_response
from joshu.tools.system_info import get_system_info

logger = logging.getLogger(__name__)
# Reduce logging verbosity
logger.setLevel(logging.WARNING)

# Global variable to store the connection status
_connection_established = False
_connection_error = None

def establish_openrouter_connection(model_name: Optional[str] = None) -> bool:
    """Establish connection to OpenRouter service."""
    global _connection_established, _connection_error
    
    if _connection_established:
        return True
    
    try:
        client = get_openrouter_client(model_name)
        if client:
            # Test the connection with a simple request
            _connection_established = True
            _connection_error = None
            logger.debug("Connection to OpenRouter established successfully")
            return True
    except Exception as e:
        _connection_error = str(e)
        logger.debug(f"Failed to establish OpenRouter connection: {e}")
        return False
    
    return False


def get_openrouter_client(model_name: Optional[str] = None) -> Optional[OpenAI]:
    """Get OpenRouter client using centralized configuration."""
    api_key = ModelConfig.get_openrouter_api_key(model_name)
    if not api_key:
        return None
    return OpenAI(base_url="https://openrouter.ai/api/v1", api_key=api_key)


def chat_completion(
    messages: List[Dict[str, str]],
    model: Optional[str] = None,
    extra_headers: Optional[Dict[str, str]] = None,
    temperature: float = 0.1,
    max_tokens: int = 512,
) -> Optional[str]:
    """Chat completion using OpenRouter (backward compatible wrapper)."""
    # Use centralized config
    if model is None or model == "default":
        model_name = ModelConfig.get_openrouter_model(model)
    else:
        model_name = model
    
    # Check connection status
    global _connection_established, _connection_error
    if not _connection_established:
        logger.debug("Attempting to establish OpenRouter connection...")
        establish_openrouter_connection(model_name)
    
    client = get_openrouter_client(model_name)
    if client is None:
        return None

    headers = ModelConfig.get_openrouter_headers()
    if extra_headers:
        headers.update({k: v for k, v in extra_headers.items() if v})

    try:
        completion = client.chat.completions.create(
            extra_headers=headers,
            model=model_name,
            messages=messages,  # type: ignore
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return completion.choices[0].message.content  # type: ignore[no-any-return]
    except Exception as e:
        logger.debug(f"Multi-provider API call failed: {e}")
        return None


def translate_command_with_openrouter(prompt: str) -> Optional[Dict[str, str]]:
    """Translate natural language to command using multi-provider API."""
    system_info = get_system_info()
    system_prompt = f"""You are a CLI assistant that translates natural language to shell commands.
The user is on a {system_info} system. Generate appropriate commands for this platform.
Respond ONLY with a JSON object containing "command" and "explanation" fields.
Example response:
{{"command": "dir", "explanation": "List all files and directories in the current directory"}}

User request:"""
    
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": prompt}
    ]
    
    # Use centralized config
    model_name = ModelConfig.get_openrouter_model()
    response = chat_completion(messages, model=model_name, temperature=0.1, max_tokens=256)
    if not response:
        return None
        
    # Use shared utility for JSON parsing
    data = parse_json_response(response)
    if data:
        command = data.get("command", "").strip()
        explanation = data.get("explanation", "").strip()
        
        if command and explanation:
            return {"command": command, "explanation": explanation}
    
    return None
