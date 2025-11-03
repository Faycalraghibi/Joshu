"""Llama.cpp model provider and wrapper."""

from __future__ import annotations

import os
from typing import Any, Dict, Generator, Optional

try:
    from llama_cpp import Llama  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    Llama = None  # type: ignore

import logging

from ..base import ModelProvider
from ..config import ModelConfig

logger = logging.getLogger(__name__)


class LlamaCppWrapper:
    """Wrapper for llama.cpp models."""
    
    def __init__(self, model_path: str, n_ctx: int = 4096, n_threads: int | None = None, 
                 n_gpu_layers: int = 0, seed: int = 42) -> None:
        if Llama is None:
            raise RuntimeError("llama-cpp-python is not installed")
        
        self.model_path = model_path
        self.n_ctx = n_ctx
        self.n_threads = n_threads
        self.n_gpu_layers = n_gpu_layers
        self.seed = seed
        
        # Initialize the model with memory-efficient settings
        self._llm = Llama(
            model_path=model_path,
            n_ctx=n_ctx,
            n_threads=n_threads,
            n_gpu_layers=n_gpu_layers,
            seed=seed,
            use_mlock=False,  # Don't lock memory to be more memory-efficient
            use_mmap=True,    # Use memory mapping for better memory usage
            logits_all=False, # Don't compute logits for all tokens to save memory
            embedding=False,  # Disable embedding mode to save memory
        )

    def generate(self, prompt: str, max_tokens: int = 256, temperature: float = 0.1,
                 top_p: float = 0.95, top_k: int = 40, repeat_penalty: float = 1.1) -> str:
        """Generate a response with memory-efficient parameters."""
        output = self._llm(
            prompt,
            max_tokens=max_tokens,
            temperature=temperature,
            top_p=top_p,
            top_k=top_k,
            repeat_penalty=repeat_penalty,
            stop=["</s>", "</assistant>", "</user>"],
        )
        text = output.get("choices", [{}])[0].get("text", "")
        return text.strip()
    
    def generate_stream(self, prompt: str, max_tokens: int = 256, temperature: float = 0.1,
                        top_p: float = 0.95, top_k: int = 40, repeat_penalty: float = 1.1) -> Generator[str, None, None]:
        """Generate a streaming response."""
        # Use the streaming completion API
        completion = self._llm.create_completion(
            prompt,
            max_tokens=max_tokens,
            temperature=temperature,
            top_p=top_p,
            top_k=top_k,
            repeat_penalty=repeat_penalty,
            stop=["</s>", "</assistant>", "</user>"],
            stream=True,
        )
        
        for chunk in completion:
            text = chunk.get("choices", [{}])[0].get("text", "")
            if text:
                yield text
    
    def get_model_info(self) -> dict[str, Any]:
        """Get information about the loaded model."""
        return {
            "model_path": self.model_path,
            "n_ctx": self.n_ctx,
            "n_threads": self.n_threads,
            "n_gpu_layers": self.n_gpu_layers,
            "seed": self.seed,
        }


def maybe_load_llama_from_env() -> Optional[LlamaCppWrapper]:
    """Load a llama model from environment variables."""
    model_path = os.getenv("JOSHU_LLAMA_CPP_MODEL")
    if not model_path:
        return None
    try:
        # Get additional configuration from environment variables
        llama_config = ModelConfig.get_llama_config()
        return LlamaCppWrapper(
            model_path,
            llama_config["n_ctx"],
            llama_config["n_threads"],
            llama_config["n_gpu_layers"],
            llama_config["seed"],
        )
    except Exception:
        return None


class LlamaCppProvider(ModelProvider):
    """Provider for llama.cpp models."""
    
    def __init__(self, model_name: str, config: Optional[Dict[str, Any]] = None) -> None:
        """
        Initialize llama.cpp provider.
        
        Args:
            model_name: Name of the local model to load
            config: Optional configuration dictionary
        """
        config = config or {}
        super().__init__(name=f"llama-cpp-{model_name}", config=config)
        self.model_name = model_name
        self._llama: Optional[LlamaCppWrapper] = None
        self.model_path: Optional[str] = None
    
    def initialize(self) -> bool:
        """Initialize llama.cpp model."""
        if self._initialized:
            return True
        
        try:
            # Get model path
            self.model_path = ModelConfig.get_local_model_path(self.model_name)
            if not self.model_path:
                logger.debug(f"Model path not found for {self.model_name}")
                return False
            
            # Get llama config
            llama_config = ModelConfig.get_llama_config()
            
            # Load model
            self._llama = LlamaCppWrapper(
                model_path=self.model_path,
                n_ctx=llama_config["n_ctx"],
                n_threads=llama_config["n_threads"],
                n_gpu_layers=llama_config["n_gpu_layers"],
                seed=llama_config["seed"],
            )
            
            self._initialized = True
            self._available = True
            logger.debug(f"Llama.cpp provider initialized: {self.model_name}")
            return True
        except Exception as e:
            logger.debug(f"Failed to initialize llama.cpp provider: {e}")
            self._initialized = False
            self._available = False
            return False
    
    def is_available(self) -> bool:
        """Check if llama.cpp model is available."""
        return self._initialized and self._llama is not None
    
    def generate(
        self,
        prompt: str,
        *,
        temperature: float = 0.1,
        max_tokens: int = 512,
        **kwargs: Any,
    ) -> str:
        """Generate response using llama.cpp model."""
        if not self.is_available():
            if not self.initialize():
                raise RuntimeError(f"Llama.cpp provider {self.model_name} is not available")
        
        if not self._llama:
            raise RuntimeError("Llama model not loaded")
        
        top_p = kwargs.get("top_p", 0.95)
        top_k = kwargs.get("top_k", 40)
        repeat_penalty = kwargs.get("repeat_penalty", 1.1)
        
        return self._llama.generate(
            prompt=prompt,
            max_tokens=max_tokens,
            temperature=temperature,
            top_p=top_p,
            top_k=top_k,
            repeat_penalty=repeat_penalty,
        )
    
    def generate_stream(
        self,
        prompt: str,
        *,
        temperature: float = 0.1,
        max_tokens: int = 512,
        **kwargs: Any,
    ) -> Generator[str, None, None]:
        """Generate streaming response using llama.cpp model."""
        if not self.is_available():
            if not self.initialize():
                raise RuntimeError(f"Llama.cpp provider {self.model_name} is not available")
        
        if not self._llama:
            raise RuntimeError("Llama model not loaded")
        
        top_p = kwargs.get("top_p", 0.95)
        top_k = kwargs.get("top_k", 40)
        repeat_penalty = kwargs.get("repeat_penalty", 1.1)
        
        yield from self._llama.generate_stream(
            prompt=prompt,
            max_tokens=max_tokens,
            temperature=temperature,
            top_p=top_p,
            top_k=top_k,
            repeat_penalty=repeat_penalty,
        )
    
    def cleanup(self) -> None:
        """Cleanup llama.cpp model."""
        super().cleanup()
        self._llama = None
        self.model_path = None
