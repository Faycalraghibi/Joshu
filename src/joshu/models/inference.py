from __future__ import annotations

import os
import logging
from typing import Dict, Optional, Generator
from threading import Lock

from .local_models import EchoModel
from .llm_interface import LLM
from .llama_cpp_loader import LlamaCppWrapper, maybe_load_llama_from_env
from .openrouter import get_openrouter_client, chat_completion

# Set up logging with reduced verbosity - only show warnings and errors
logger = logging.getLogger(__name__)
logger.setLevel(logging.WARNING)

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

# Global variable to track if connection has been established
_connection_established = False

def establish_model_connection(model_name: str) -> bool:
    """Establish connection to the model service."""
    global _connection_established
    
    if _connection_established:
        return True
    
    try:
        # Check if OpenRouter API key is available or model-specific keys
        openrouter_key = os.getenv("OPENROUTER_API_KEY")
        
        # Also check for model-specific API keys
        model_specific_keys = [
            "DEEPSEEK_API_KEY",
            "TONGYI_API_KEY", 
            "QWEN_API_KEY",
            "KIMI_DEV_API_KEY",
            "AGENTICAT_API_KEY",
            "GLM_API_KEY"
        ]
        
        has_model_specific_key = any(os.getenv(key) for key in model_specific_keys)
        
        # Auto-enable cloud if API key is present (unless explicitly disabled)
        use_cloud_env = os.getenv("JOSHU_USE_CLOUD", "").lower()
        if use_cloud_env == "false":
            use_cloud = False
        elif use_cloud_env == "true":
            use_cloud = True
        elif openrouter_key or has_model_specific_key:
            use_cloud = True  # Auto-enable if API key found
            logger.debug("Auto-enabling cloud mode due to API key presence")
        else:
            use_cloud = False
        
        if (openrouter_key or has_model_specific_key) and use_cloud:
            # Try to establish connection to OpenRouter
            from .openrouter import establish_openrouter_connection
            if establish_openrouter_connection(model_name):
                _connection_established = True
                logger.debug("Cloud model connection established")
                return True
        
        # For local models, just try to load the model
        model = _load_local_model(model_name)
        if model is not None:
            _model_cache[model_name] = model
            _connection_established = True
            logger.debug("Local model loaded successfully")
            return True
            
        # Try to load default local llama model
        llama = maybe_load_llama_from_env()
        if llama is not None:
            # Adapt to LLM interface with a lightweight wrapper
            class LlamaAdapter(LLM):
                def generate(self, prompt: str, **kwargs):
                    return llama.generate(prompt, **kwargs)

            model = LlamaAdapter()
            _model_cache[model_name] = model
            _connection_established = True
            logger.debug("Default local model loaded successfully")
            return True
            
    except Exception as e:
        logger.debug(f"Failed to establish model connection: {e}")
        return False
    
    return False


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
    global _model_cache, _connection_established
    
    with _model_lock:
        # Return cached model if available
        if model_name in _model_cache:
            return _model_cache[model_name]
        
        # Try to establish connection if not already done
        if not _connection_established:
            logger.debug("Attempting to establish model connection...")
            establish_model_connection(model_name)
        
        # Check if OpenRouter API key is available or model-specific keys
        openrouter_key = os.getenv("OPENROUTER_API_KEY")
        
        # Check for model-specific API keys that work with OpenRouter
        model_specific_keys = [
            "DEEPSEEK_API_KEY",
            "TONGYI_API_KEY", 
            "QWEN_API_KEY",
            "KIMI_DEV_API_KEY",
            "AGENTICAT_API_KEY",
            "GLM_API_KEY"
        ]
        has_model_key = any(os.getenv(key) for key in model_specific_keys)
        
        # Check cloud setting - auto-enable if API key is present unless explicitly disabled
        use_cloud_env = os.getenv("JOSHU_USE_CLOUD", "").lower()
        
        # Determine if we should use cloud:
        # 1. If explicitly set to "false", don't use cloud (unless forced)
        # 2. If explicitly set to "true", use cloud
        # 3. If not set but we have an API key, auto-enable cloud
        if use_cloud_env == "false":
            use_cloud = False
            logger.debug("JOSHU_USE_CLOUD explicitly set to false")
        elif use_cloud_env == "true":
            use_cloud = True
            logger.debug("JOSHU_USE_CLOUD explicitly set to true")
        elif openrouter_key or has_model_key:
            # Auto-enable if API key is present
            use_cloud = True
            logger.debug("JOSHU_USE_CLOUD not set, but API key found - enabling cloud mode automatically")
        else:
            use_cloud = False
        
        # Use OpenRouter if we have ANY API key (OpenRouter or model-specific) and cloud is enabled
        should_use_openrouter = (openrouter_key or has_model_key) and use_cloud
        
        if should_use_openrouter:
            # Use OpenRouter model
            # Determine which model to use: prefer OPENROUTER_MODEL env var, or use provided model_name if it looks like a cloud model
            openrouter_model = os.getenv("OPENROUTER_MODEL")
            # If model_name is a local model name (like "llama-3-8b") but we have OPENROUTER_MODEL set, use that
            # Otherwise, if model_name looks like a cloud model (contains /), use it
            if openrouter_model:
                actual_model = openrouter_model
            elif "/" in model_name or model_name.startswith("openai/") or model_name.startswith("deepseek/"):
                actual_model = model_name
            else:
                # Default to a cloud model
                actual_model = openrouter_model or "openai/gpt-4o-mini"
            
            logger.info(f"Using OpenRouter API with model: {actual_model}")
            
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
            
            model = OpenRouterModel(actual_model)
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
    model_path_env = f"JOSHU_MODEL_{model_name.upper().replace('-', '_')}"
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