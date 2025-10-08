from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

from openai import OpenAI


def get_openrouter_client() -> Optional[OpenAI]:
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        return None
    return OpenAI(base_url="https://openrouter.ai/api/v1", api_key=api_key)


def chat_completion(
    messages: List[Dict[str, str]],
    model: Optional[str] = None,
    extra_headers: Optional[Dict[str, str]] = None,
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

    completion = client.chat.completions.create(
        extra_headers=headers,
        model=model_name,
        messages=messages,
    )
    try:
        return completion.choices[0].message.content  # type: ignore[no-any-return]
    except Exception:
        return None


