from __future__ import annotations

import os
import json
import logging
import platform
from typing import Any, Dict, List, Optional

from openai import OpenAI

logger = logging.getLogger(__name__)

def get_system_info() -> str:
    """Get information about the current system for command generation."""
    system = platform.system()
    if system == "Windows":
        return "Windows"
    elif system == "Darwin":
        return "macOS"
    elif system == "Linux":
        return "Linux"
    else:
        return f"Unix-like ({system})"


def get_openrouter_client() -> Optional[OpenAI]:
    api_key = os.getenv("OPENROUTER_API_KEY")
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
    client = get_openrouter_client()
    if client is None:
        return None

    model_name = model or os.getenv("OPENROUTER_MODEL", "openai/gpt-4o")
    headers = {
        "HTTP-Referer": os.getenv("OPENROUTER_SITE_URL", ""),
        "X-Title": os.getenv("OPENROUTER_SITE_TITLE", "OpenCLI Assistant"),
    }
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
        logger.error(f"OpenRouter API call failed: {e}")
        return None


def translate_command_with_openrouter(prompt: str) -> Optional[Dict[str, str]]:
    """Translate natural language to command using OpenRouter."""
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
    
    response = chat_completion(messages, temperature=0.1, max_tokens=256)
    if not response:
        return None
        
    try:
        # Clean up the response to handle markdown code blocks
        cleaned_response = response.strip()
        if cleaned_response.startswith("```json"):
            cleaned_response = cleaned_response[7:]  # Remove ```json
        if cleaned_response.startswith("```"):
            cleaned_response = cleaned_response[3:]  # Remove ```
        if cleaned_response.endswith("```"):
            cleaned_response = cleaned_response[:-3]  # Remove ```
        
        # Parse JSON response
        data = json.loads(cleaned_response)
        command = data.get("command", "").strip()
        explanation = data.get("explanation", "").strip()
        
        if command and explanation:
            return {"command": command, "explanation": explanation}
    except json.JSONDecodeError:
        logger.warning(f"Failed to parse OpenRouter response as JSON: {response}")
        return None
    
    return None