"""vLLM/LM Studio API provider implementation."""

from __future__ import annotations

import logging
import os
import json
from typing import Any, Dict, List, Optional

import requests

from ..base import ModelProvider
from ..config import ModelConfig

logger = logging.getLogger(__name__)


class VLLMProvider(ModelProvider):
    """Provider for vLLM/LM Studio API models."""
    
    def __init__(self, model_name: Optional[str] = None, config: Optional[Dict[str, Any]] = None) -> None:
        """
        Initialize vLLM provider.
        
        Args:
            model_name: Model identifier to use (if None, will use config default)
            config: Optional configuration dictionary
        """
        config = config or {}
        super().__init__(name="vllm", config=config)
        self.model_name = model_name or ModelConfig.get_vllm_model_identifier()
        self.base_url = ModelConfig.get_vllm_url()
        self._available = False
    
    def initialize(self) -> bool:
        """Initialize vLLM provider."""
        if self._initialized:
            return True
        
        try:
            if not self.base_url:
                logger.debug("No vLLM URL configured")
                return False
            
            if not self.model_name:
                logger.debug("No vLLM model identifier configured")
                return False
            
            # Test connection with a simple health check or test request
            try:
                # Try to make a simple request to verify connection
                test_response = requests.post(
                    self.base_url,
                    headers={"Content-Type": "application/json"},
                    json={
                        "model": self.model_name,
                        "messages": [{"role": "user", "content": "test"}],
                        "max_tokens": 1
                    },
                    timeout=5
                )
                if test_response.status_code == 200:
                    self._initialized = True
                    self._available = True
                    logger.debug(f"vLLM provider initialized with URL: {self.base_url}, model: {self.model_name}")
                    return True
                else:
                    logger.debug(f"vLLM provider health check failed: {test_response.status_code}")
                    return False
            except requests.exceptions.RequestException as e:
                logger.debug(f"vLLM provider connection test failed: {e}")
                return False
        except Exception as e:
            logger.debug(f"Failed to initialize vLLM provider: {e}")
            self._initialized = False
            self._available = False
            return False
    
    def is_available(self) -> bool:
        """Check if vLLM is available."""
        if not self._initialized:
            return False
        
        # Check if URL and model are still configured
        return (self.base_url is not None and 
                self.model_name is not None)
    
    def generate(
        self,
        prompt: str,
        *,
        temperature: float = 0.1,
        max_tokens: int = 512,
        **kwargs: Any,
    ) -> str:
        """Generate response using vLLM API."""
        if not self.is_available():
            if not self.initialize():
                raise RuntimeError("vLLM provider is not available")
        
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
        """Generate chat completion using vLLM API."""
        if not self.is_available():
            if not self.initialize():
                logger.debug("vLLM provider not available for chat completion")
                return None
        
        try:
            # Prepare request payload
            data = {
                "model": self.model_name,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens if max_tokens > 0 else -1,  # -1 means no limit
                **kwargs  # Allow additional parameters
            }
            
            # Add system message if not present
            if messages and messages[0].get("role") != "system":
                data["messages"] = [
                    {"role": "system", "content": "You are a helpful assistant."},
                    *messages
                ]
            
            # Send request
            response = requests.post(
                self.base_url,
                headers={"Content-Type": "application/json"},
                data=json.dumps(data),
                timeout=kwargs.get("timeout", 60)
            )
            
            if response.status_code == 200:
                response_data = response.json()
                # Extract the content from the response
                if "choices" in response_data and len(response_data["choices"]) > 0:
                    return response_data["choices"][0]["message"]["content"]
                else:
                    logger.warning(f"Unexpected vLLM response format: {response_data}")
                    return None
            else:
                logger.debug(f"vLLM API call failed: Status {response.status_code} - {response.text}")
                return None
        except requests.exceptions.RequestException as e:
            logger.debug(f"vLLM API call failed: {e}")
            return None
        except Exception as e:
            logger.debug(f"Error processing vLLM response: {e}")
            return None
    
    def cleanup(self) -> None:
        """Cleanup vLLM provider resources."""
        super().cleanup()
        self.base_url = None
        self.model_name = None

