"""
Local model provider for local model API servers.

This provider connects to local model API servers that provide OpenAI-compatible
chat completion endpoints.
"""

from __future__ import annotations

import logging
import os
import json
from typing import Any, Dict, List, Optional

import requests

from ..base import ModelProvider
from ..config import ModelConfig

logger = logging.getLogger(__name__)


class LocalModelProvider(ModelProvider):
    """
    Provider for local model API servers.
    
    This provider connects to local model API servers that provide OpenAI-compatible
    chat completion endpoints. Configure using LOCAL_MODEL_URL and LOCAL_MODEL_IDENTIFIER
    environment variables.
    """
    
    def __init__(self, model_name: Optional[str] = None, config: Optional[Dict[str, Any]] = None) -> None:
        """
        Initialize local model provider.
        
        Args:
            model_name: Model identifier to use (if None, will use config default)
            config: Optional configuration dictionary
        """
        config = config or {}
        super().__init__(name="local", config=config)
        self.model_name = model_name or ModelConfig.get_local_model_api_identifier()
        base_url = ModelConfig.get_local_model_api_url()
        # Ensure URL includes the endpoint path if not already present
        if base_url and not base_url.endswith('/v1/chat/completions'):
            # If URL doesn't end with /v1/chat/completions, append it
            # Handle both cases: with or without trailing slash
            base_url = base_url.rstrip('/') + '/v1/chat/completions'
        self.base_url = base_url
        self._available = False
    
    def initialize(self) -> bool:
        """Initialize local model provider."""
        if self._initialized:
            return True
        
        try:
            if not self.base_url:
                logger.debug("No local model API URL configured")
                return False
            
            if not self.model_name:
                logger.debug("No local model identifier configured")
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
                    logger.debug(f"Local model provider initialized with URL: {self.base_url}, model: {self.model_name}")
                    return True
                else:
                    logger.debug(f"Local model provider health check failed: {test_response.status_code}")
                    return False
            except requests.exceptions.RequestException as e:
                logger.debug(f"Local model provider connection test failed: {e}")
                return False
        except Exception as e:
            logger.debug(f"Failed to initialize local model provider: {e}")
            self._initialized = False
            self._available = False
            return False
    
    def is_available(self) -> bool:
        """Check if local model provider is available."""
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
        """Generate response using local model API."""
        if not self.is_available():
            if not self.initialize():
                raise RuntimeError("Local model provider is not available")
        
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
        """Generate chat completion using local model API."""
        if not self.is_available():
            if not self.initialize():
                logger.debug("Local model provider not available for chat completion")
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
                    logger.warning(f"Unexpected local model API response format: {response_data}")
                    return None
            else:
                logger.debug(f"Local model API call failed: Status {response.status_code} - {response.text}")
                return None
        except requests.exceptions.RequestException as e:
            logger.debug(f"Local model API call failed: {e}")
            return None
        except Exception as e:
            logger.debug(f"Error processing local model API response: {e}")
            return None
    
    def cleanup(self) -> None:
        """Cleanup local model provider resources."""
        super().cleanup()
        self.base_url = None
        self.model_name = None


