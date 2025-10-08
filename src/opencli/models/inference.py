from __future__ import annotations

import os
from typing import Dict, Optional

from .local_models import EchoModel
from .llm_interface import LLM
from .llama_cpp_loader import maybe_load_llama_from_env
from .openrouter import get_openrouter_client, chat_completion


def get_model(model_name: str) -> LLM:
    # Check if OpenRouter API key is available and user wants to use cloud models
    openrouter_key = os.getenv("OPENROUTER_API_KEY")
    use_cloud = os.getenv("OPENCLI_USE_CLOUD", "false").lower() == "true"
    
    if openrouter_key and use_cloud:
        # Use OpenRouter model
        class OpenRouterModel(LLM):
            def __init__(self, model_name: str) -> None:
                self.model_name = model_name
            
            def generate(self, prompt: str, **kwargs) -> str:
                messages = [
                    {"role": "user", "content": prompt}
                ]
                response = chat_completion(messages, model=self.model_name)
                return response or "No response from OpenRouter"
        
        return OpenRouterModel(model_name)
    
    # Try to load local llama model
    llama = maybe_load_llama_from_env()
    if llama is not None:
        # Adapt to LLM interface with a lightweight wrapper
        class _Adapter(LLM):
            def generate(self, prompt: str, **kwargs):
                return llama.generate(prompt, **kwargs)

        return _Adapter()
    
    # Fallback to echo model
    return EchoModel()