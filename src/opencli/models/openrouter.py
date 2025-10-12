from __future__ import annotations

import os
import json
import logging
import platform
from typing import Any, Dict, List, Optional

from openai import OpenAI
from opencli.tools.system_info import get_system_info

logger = logging.getLogger(__name__)




def get_openrouter_client(model_name: Optional[str] = None) -> Optional[OpenAI]:
    # Determine which API key to use based on the model
    api_key = None
    if model_name:
        # Check for model-specific API keys
        if "deepseek" in model_name.lower():
            api_key = os.getenv("DEEPSEEK_API_KEY")
        elif "tongyi" in model_name.lower():
            api_key = os.getenv("TONGYI_API_KEY")
        elif "qwen" in model_name.lower():
            api_key = os.getenv("QWEN_API_KEY")
        elif "kimi" in model_name.lower():
            api_key = os.getenv("KIMI_DEV_API_KEY")
        elif "agentica" in model_name.lower():
            api_key = os.getenv("AGENTICAT_API_KEY")
    
    # Fallback to general OpenRouter API key
    if not api_key:
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
    # Use DeepSeek model as default if specified, otherwise fall back to environment default
    model_name = model or os.getenv("DEEPSEEK_URL") or "deepseek/deepseek-chat-v3.1:free"
    client = get_openrouter_client(model_name)
    if client is None:
        return None

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
        logger.error(f"Multi-provider API call failed: {e}")
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
        logger.warning(f"Failed to parse multi-provider response as JSON: {response}")
        return None
    
    return None