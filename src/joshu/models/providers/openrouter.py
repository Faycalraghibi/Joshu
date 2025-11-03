"""OpenRouter API provider implementation."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from openai import OpenAI

from ..base import ModelProvider
from ..config import ModelConfig

logger = logging.getLogger(__name__)


class OpenRouterProvider(ModelProvider):
    """Provider for OpenRouter API models."""
    
    def __init__(self, model_name: Optional[str] = None, config: Optional[Dict[str, Any]] = None) -> None:
        """
        Initialize OpenRouter provider.
        
        Args:
            model_name: Model name to use (if None, will use config default)
            config: Optional configuration dictionary
        """
        config = config or {}
        super().__init__(name="openrouter", config=config)
        self.model_name = model_name or ModelConfig.get_openrouter_model(model_name)
        self._client: Optional[OpenAI] = None
        self._connection_established = False
    
    def initialize(self) -> bool:
        """Initialize OpenRouter client."""
        if self._initialized:
            return True
        
        try:
            api_key = ModelConfig.get_openrouter_api_key(self.model_name)
            if not api_key:
                logger.debug("No API key available for OpenRouter")
                return False
            
            self._client = OpenAI(
                base_url="https://openrouter.ai/api/v1",
                api_key=api_key
            )
            self._initialized = True
            self._available = True
            self._connection_established = True
            logger.debug(f"OpenRouter provider initialized with model: {self.model_name}")
            return True
        except Exception as e:
            logger.debug(f"Failed to initialize OpenRouter provider: {e}")
            self._initialized = False
            self._available = False
            return False
    
    def is_available(self) -> bool:
        """Check if OpenRouter is available."""
        if not self._initialized:
            return False
        
        # Check if API key is still available
        api_key = ModelConfig.get_openrouter_api_key(self.model_name)
        return api_key is not None and self._client is not None
    
    def generate(
        self,
        prompt: str,
        *,
        temperature: float = 0.1,
        max_tokens: int = 512,
        **kwargs: Any,
    ) -> str:
        """Generate response using OpenRouter API."""
        if not self.is_available():
            if not self.initialize():
                raise RuntimeError("OpenRouter provider is not available")
        
        # Convert prompt to messages format
        messages = [{"role": "user", "content": prompt}]
        return self.chat_completion(messages, temperature=temperature, max_tokens=max_tokens, **kwargs) or ""
    
    def chat_completion(
        self,
        messages: List[Dict[str, str]],
        *,
        temperature: float = 0.1,
        max_tokens: int = 512,
        **kwargs: Any,
    ) -> Optional[str]:
        """Generate chat completion using OpenRouter API."""
        if not self.is_available():
            if not self.initialize():
                logger.debug("OpenRouter provider not available for chat completion")
                return None
        
        if not self._client:
            return None
        
        try:
            headers = ModelConfig.get_openrouter_headers()
            extra_headers = kwargs.get("extra_headers", {})
            if extra_headers:
                headers.update({k: v for k, v in extra_headers.items() if v})
            
            completion = self._client.chat.completions.create(
                extra_headers=headers,
                model=self.model_name,
                messages=messages,  # type: ignore
                temperature=temperature,
                max_tokens=max_tokens,
            )
            return completion.choices[0].message.content  # type: ignore[no-any-return]
        except Exception as e:
            logger.debug(f"OpenRouter API call failed: {e}")
            return None
    
    def cleanup(self) -> None:
        """Cleanup OpenRouter client."""
        super().cleanup()
        self._client = None
        self._connection_established = False


