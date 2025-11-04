"""Centralized configuration management for model providers."""

from __future__ import annotations

import os
import logging
from typing import Dict, List, Optional, Set

logger = logging.getLogger(__name__)


class ModelConfig:
    """Centralized configuration manager for model providers."""
    
    # Model-specific API key mappings
    MODEL_API_KEYS: Dict[str, str] = {
        "deepseek": "DEEPSEEK_API_KEY",
        "tongyi": "TONGYI_API_KEY",
        "qwen": "QWEN_API_KEY",
        "kimi": "KIMI_DEV_API_KEY",
        "agentica": "AGENTICAT_API_KEY",
        "glm": "GLM_API_KEY",
    }
    
    # Cloud model identifiers
    CLOUD_MODELS: Set[str] = {"deepseek", "tongyi", "qwen", "kimi", "agentica", "glm"}
    
    # Supported local models and their environment variable mappings
    SUPPORTED_LOCAL_MODELS: Dict[str, str] = {
        "llama-3-8b": "LLAMA_CPP_MODEL_LLAMA3_8B",
        "llama-3-70b": "LLAMA_CPP_MODEL_LLAMA3_70B",
        "mistral-7b": "LLAMA_CPP_MODEL_MISTRAL_7B",
        "codellama-34b": "LLAMA_CPP_MODEL_CODELLAMA_34B",
        "gemma-2-9b": "LLAMA_CPP_MODEL_GEMMA_2_9B",
    }
    
    @classmethod
    def get_openrouter_api_key(cls, model_name: Optional[str] = None) -> Optional[str]:
        """
        Get the appropriate OpenRouter API key based on model name.
        
        Args:
            model_name: Optional model name to determine API key
        Returns:
            API key string or None if not found
        """
        # Try model-specific key first
        if model_name:
            model_lower = model_name.lower()
            for cloud_model, env_key in cls.MODEL_API_KEYS.items():
                if cloud_model in model_lower:
                    api_key = os.getenv(env_key)
                    if api_key:
                        return api_key
        
        # Fallback to general OpenRouter key
        api_key = os.getenv("OPENROUTER_API_KEY")
        if api_key:
            return api_key
        
        # Try any available model-specific key
        for env_key in cls.MODEL_API_KEYS.values():
            api_key = os.getenv(env_key)
            if api_key:
                return api_key
        
        return None
    
    @classmethod
    def has_any_api_key(cls) -> bool:
        """
        Check if any API key is available.
        
        Returns:
            True if any API key is found, False otherwise
        """
        return cls.get_openrouter_api_key() is not None
    
    @classmethod
    def should_use_cloud(cls) -> bool:
        """
        Determine if cloud models should be used.
        
        Logic:
        1. If JOSHU_USE_CLOUD is explicitly "false", don't use cloud
        2. If JOSHU_USE_CLOUD is explicitly "true", use cloud
        3. If not set but API key is present, auto-enable cloud
        4. Otherwise, don't use cloud
        
        Returns:
            True if cloud should be used, False otherwise
        """
        use_cloud_env = os.getenv("JOSHU_USE_CLOUD", "").lower()
        
        if use_cloud_env == "false":
            return False
        elif use_cloud_env == "true":
            return True
        elif cls.has_any_api_key():
            # Auto-enable if API key is present
            return True
        else:
            return False
    
    @classmethod
    def is_cloud_model(cls, model_name: str) -> bool:
        """
        Check if a model name indicates a cloud model.
        
        Args:
            model_name: Model name to check
        
        Returns:
            True if this appears to be a cloud model, False otherwise
        """
        model_lower = model_name.lower()
        
        # Check if it contains cloud model identifiers
        if any(cloud_model in model_lower for cloud_model in cls.CLOUD_MODELS):
            return True
        
        # Check if it has a slash (e.g., "openai/gpt-4o-mini")
        if "/" in model_name:
            return True
        
        return False
    
    @classmethod
    def get_openrouter_model(cls, model_name: Optional[str] = None) -> str:
        """
        Get the OpenRouter model name to use.
        
        Args:
            model_name: Optional requested model name
        
        Returns:
            Model name string for OpenRouter
        """
        # Use explicit OPENROUTER_MODEL env var if set
        env_model = os.getenv("OPENROUTER_MODEL")
        if env_model:
            return env_model
        
        # If model_name looks like a cloud model, use it
        if model_name and cls.is_cloud_model(model_name):
            return model_name
        
        # Default fallback
        return "openai/gpt-4o-mini"
    
    @classmethod
    def get_local_model_path(cls, model_name: str) -> Optional[str]:
        """
        Get the file path for a local model.
        
        Args:
            model_name: Local model name
        
        Returns:
            File path string or None if not found
        """
        # Check supported local models
        if model_name in cls.SUPPORTED_LOCAL_MODELS:
            env_var = cls.SUPPORTED_LOCAL_MODELS[model_name]
            model_path = os.getenv(env_var)
            if model_path and os.path.exists(model_path):
                return model_path
        
        # Try generic model path pattern
        model_path_env = f"JOSHU_MODEL_{model_name.upper().replace('-', '_')}"
        model_path = os.getenv(model_path_env)
        if model_path and os.path.exists(model_path):
            return model_path
        
        # Try generic LLAMA_CPP_MODEL
        model_path = os.getenv("JOSHU_LLAMA_CPP_MODEL")
        if model_path and os.path.exists(model_path):
            return model_path
        
        return None
    
    @classmethod
    def get_llama_config(cls) -> Dict[str, Any]:
        """
        Get llama.cpp configuration from environment variables.
        
        Returns:
            Dictionary with llama.cpp configuration
        """
        return {
            "n_ctx": int(os.getenv("JOSHU_LLAMA_CTX_SIZE", "4096")),
            "n_threads": int(os.getenv("JOSHU_LLAMA_THREADS", "0")) or None,
            "n_gpu_layers": int(os.getenv("JOSHU_LLAMA_GPU_LAYERS", "0")),
            "seed": int(os.getenv("JOSHU_LLAMA_SEED", "42")),
        }
    
    @classmethod
    def get_openrouter_headers(cls) -> Dict[str, str]:
        """
        Get OpenRouter HTTP headers.
        
        Returns:
            Dictionary of HTTP headers for OpenRouter requests
        """
        return {
            "HTTP-Referer": os.getenv("OPENROUTER_SITE_URL", ""),
            "X-Title": os.getenv("OPENROUTER_SITE_TITLE", "Joshu Assistant"),
        }
    
    @classmethod
    def get_vllm_url(cls) -> Optional[str]:
        """
        Get vLLM/LM Studio API URL from environment.
        
        Returns:
            API URL string or None if not found
        """
        return os.getenv("VLLM_URL") or os.getenv("LM_STUDIO_URL")
    
    @classmethod
    def get_vllm_model_identifier(cls) -> Optional[str]:
        """
        Get vLLM/LM Studio model identifier from environment.
        
        Returns:
            Model identifier string or None if not found
        """
        return os.getenv("VLLM_MODEL_IDENTIFIER") or os.getenv("LM_STUDIO_MODEL_IDENTIFIER") or os.getenv("VLLM_MODEL")


