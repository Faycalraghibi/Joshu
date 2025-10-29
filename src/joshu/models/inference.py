from __future__ import annotations

import os
from typing import Dict, Optional, Generator
from threading import Lock

from .local_models import EchoModel
from .llm_interface import LLM
from .llama_cpp_loader import LlamaCppWrapper, maybe_load_llama_from_env
from .openrouter import get_openrouter_client, chat_completion

# Model cache to support model loading/unloading
_model_cache: Dict[str, LLM] = {}
_model_lock = Lock()

# Supported local models
SUPPORTED_LOCAL_MODELS = {
    "llama-3-8b": "LLAMA_CPP_MODEL_LLAMA3_8B",
    "llama-3-70b": "LLAMA_CPP_MODEL_LLAMA3_70B",
    "mistral-7b": "LLAMA_CPP_MODEL_MISTRAL_7B",
    "codellama-34b": "LLAMA_CPP_MODEL_CODELLAMA_34B",
    "gemma-2-9b": "LLAMA_CPP_MODEL_GEMMA_2_9B"
}

class StreamingLLM(LLM):
    """Wrapper for LLMs that supports streaming responses."""
    
    def __init__(self, llm: LLM) -> None:
        self._llm = llm
    
    def generate(self, prompt: str, **kwargs) -> str:
        """Generate a complete response."""
        return self._llm.generate(prompt, **kwargs)
    
    def generate_stream(self, prompt: str, **kwargs) -> Generator[str, None, None]:
        """Generate a streaming response."""
        # For models that don't natively support streaming, 
        # we generate the full response and yield it in chunks
        full_response = self._llm.generate(prompt, **kwargs)
        # Yield in chunks for streaming effect
        chunk_size = 50
        for i in range(0, len(full_response), chunk_size):
            yield full_response[i:i + chunk_size]


def get_model(model_name: str) -> LLM:
    """Get a model instance with caching and lazy loading."""
    global _model_cache
    
    with _model_lock:
        # Return cached model if available
        if model_name in _model_cache:
            return _model_cache[model_name]
        
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
                    if response:
                        return response
                    else:
                        # Return a proper JSON response when API call fails
                        import json
                        # Extract just the user request part from the prompt for a cleaner error message
                        user_request = prompt.split("\nUser request:\n")[-1] if "\nUser request:\n" in prompt else prompt
                        return json.dumps({
                            "command": "echo \"API connection failed\"",
                            "explanation": f"Failed to get response from OpenRouter API for request: '{user_request}'. Please check your configuration or try again later."
                        })
            
            model = OpenRouterModel(model_name)
            _model_cache[model_name] = model
            return model
        
        # Try to load specific local model
        model = _load_local_model(model_name)
        if model is not None:
            # Wrap with streaming support
            streaming_model = StreamingLLM(model)
            _model_cache[model_name] = streaming_model
            return streaming_model
        
        # Try to load default local llama model
        llama = maybe_load_llama_from_env()
        if llama is not None:
            # Adapt to LLM interface with a lightweight wrapper
            class LlamaAdapter(LLM):
                def generate(self, prompt: str, **kwargs):
                    return llama.generate(prompt, **kwargs)

            model = LlamaAdapter()
            streaming_model = StreamingLLM(model)
            _model_cache[model_name] = streaming_model
            return streaming_model
        
        # Fallback to echo model
        model = EchoModel()
        _model_cache[model_name] = model
        return model


def _load_local_model(model_name: str) -> Optional[LLM]:
    """Load a specific local model by name."""
    # Check if this is a supported local model
    if model_name in SUPPORTED_LOCAL_MODELS:
        env_var = SUPPORTED_LOCAL_MODELS[model_name]
        model_path = os.getenv(env_var)
        if model_path and os.path.exists(model_path):
            try:
                llama = LlamaCppWrapper(model_path)
                class LocalModelAdapter(LLM):
                    def generate(self, prompt: str, **kwargs):
                        return llama.generate(prompt, **kwargs)
                return LocalModelAdapter()
            except Exception as e:
                print(f"Failed to load model {model_name}: {e}")
                return None
    
    # Try to load from generic model path
    model_path_env = f"OPENCLI_MODEL_{model_name.upper().replace('-', '_')}"
    model_path = os.getenv(model_path_env)
    if model_path and os.path.exists(model_path):
        try:
            llama = LlamaCppWrapper(model_path)
            class GenericModelAdapter(LLM):
                def generate(self, prompt: str, **kwargs):
                    return llama.generate(prompt, **kwargs)
            return GenericModelAdapter()
        except Exception as e:
            print(f"Failed to load model {model_name}: {e}")
            return None
    
    return None


def unload_model(model_name: str) -> bool:
    """Unload a model from cache to free memory."""
    global _model_cache
    with _model_lock:
        if model_name in _model_cache:
            del _model_cache[model_name]
            return True
        return False


def list_loaded_models() -> list[str]:
    """List all currently loaded models."""
    global _model_cache
    with _model_lock:
        return list(_model_cache.keys())


def clear_model_cache() -> None:
    """Clear all models from cache."""
    global _model_cache
    with _model_lock:
        _model_cache.clear()