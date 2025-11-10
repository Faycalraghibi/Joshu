"""vLLM inference server provider implementation."""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, Generator, List, Optional

from ..base import ModelProvider
from ..config import ModelConfig

logger = logging.getLogger(__name__)

# Try to import vLLM - optional dependency
try:
    from vllm import LLM, SamplingParams  # type: ignore
    VLLM_AVAILABLE = True
except ImportError:
    LLM = None  # type: ignore
    SamplingParams = None  # type: ignore
    VLLM_AVAILABLE = False


class VLLMServerProvider(ModelProvider):
    """
    Provider for vLLM inference server (high-throughput backend).
    
    vLLM is a high-throughput inference server that provides OpenAI-compatible
    endpoints. This provider can use vLLM in two modes:
    1. Direct programmatic API (if vLLM is installed)
    2. OpenAI-compatible HTTP endpoint (if vLLM server is running)
    """
    
    def __init__(
        self,
        model_name: Optional[str] = None,
        server_url: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Initialize vLLM server provider.
        
        Args:
            model_name: HuggingFace model name (e.g., "meta-llama/Meta-Llama-3-8B")
            server_url: Optional URL for vLLM server (if None, uses direct API)
            config: Optional configuration dictionary
        """
        config = config or {}
        super().__init__(name="vllm-server", config=config)
        self.model_name = model_name or os.getenv("VLLM_MODEL") or "meta-llama/Meta-Llama-3-8B"
        self.server_url = server_url or os.getenv("VLLM_SERVER_URL")
        self._llm: Optional[Any] = None  # vLLM LLM instance
        self._use_direct_api = not self.server_url and VLLM_AVAILABLE
    
    def initialize(self) -> bool:
        """Initialize vLLM provider."""
        if self._initialized:
            return True
        
        try:
            # If server URL is provided, use OpenAI-compatible endpoint
            if self.server_url:
                from openai import OpenAI
                self._client = OpenAI(base_url=self.server_url, api_key="not-needed")
                self._initialized = True
                self._available = True
                logger.debug(f"vLLM provider initialized with server URL: {self.server_url}")
                return True
            
            # Otherwise, try direct vLLM API if available
            if VLLM_AVAILABLE:
                try:
                    self._llm = LLM(self.model_name)
                    self._initialized = True
                    self._available = True
                    logger.debug(f"vLLM provider initialized with model: {self.model_name}")
                    return True
                except Exception as e:
                    logger.debug(f"Failed to initialize vLLM with direct API: {e}")
                    return False
            else:
                logger.debug("vLLM not available (not installed or no server URL)")
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
        
        # Check if we have either a client (server mode) or LLM instance (direct mode)
        if self.server_url:
            return hasattr(self, '_client') and self._client is not None
        else:
            return self._llm is not None
    
    def generate(
        self,
        prompt: str,
        *,
        temperature: float = 0.1,
        max_tokens: int = 512,
        **kwargs: Any,
    ) -> str:
        """Generate response using vLLM."""
        if not self.is_available():
            if not self.initialize():
                raise RuntimeError("vLLM provider is not available")
        
        try:
            # Use server endpoint if available
            if self.server_url and hasattr(self, '_client'):
                return self._generate_via_server(prompt, temperature, max_tokens, **kwargs)
            
            # Use direct API
            if self._llm:
                return self._generate_via_direct_api(prompt, temperature, max_tokens, **kwargs)
            
            raise RuntimeError("vLLM provider not properly initialized")
            
        except Exception as e:
            logger.debug(f"vLLM generation failed: {e}")
            raise RuntimeError(f"Failed to generate response: {e}") from e
    
    def _generate_via_server(
        self,
        prompt: str,
        temperature: float,
        max_tokens: int,
        **kwargs: Any,
    ) -> str:
        """Generate via OpenAI-compatible server endpoint."""
        if not hasattr(self, '_client') or not self._client:
            raise RuntimeError("vLLM client not initialized")
        
        messages = [{"role": "user", "content": prompt}]
        
        completion = self._client.chat.completions.create(
            model=self.model_name,
            messages=messages,  # type: ignore
            temperature=temperature,
            max_tokens=max_tokens,
        )
        
        return completion.choices[0].message.content or ""  # type: ignore[no-any-return]
    
    def _generate_via_direct_api(
        self,
        prompt: str,
        temperature: float,
        max_tokens: int,
        **kwargs: Any,
    ) -> str:
        """Generate via direct vLLM API."""
        if not self._llm:
            raise RuntimeError("vLLM instance not initialized")
        
        sampling_params = SamplingParams(
            temperature=temperature,
            max_tokens=max_tokens,
        )
        
        outputs = self._llm.generate([prompt], sampling_params)
        return outputs[0].outputs[0].text
    
    def generate_stream(
        self,
        prompt: str,
        *,
        temperature: float = 0.1,
        max_tokens: int = 512,
        **kwargs: Any,
    ) -> Generator[str, None, None]:
        """Generate streaming response using vLLM."""
        if not self.is_available():
            if not self.initialize():
                raise RuntimeError("vLLM provider is not available")
        
        try:
            # Use server endpoint if available (supports streaming)
            if self.server_url and hasattr(self, '_client'):
                yield from self._generate_stream_via_server(prompt, temperature, max_tokens, **kwargs)
                return
            
            # Direct API doesn't support streaming easily, fallback to chunking
            full_response = self._generate_via_direct_api(prompt, temperature, max_tokens, **kwargs)
            from joshu.tools.response_utils import chunk_response
            yield from chunk_response(full_response)
            
        except Exception as e:
            logger.debug(f"vLLM streaming failed: {e}")
            raise RuntimeError(f"Failed to generate streaming response: {e}") from e
    
    def _generate_stream_via_server(
        self,
        prompt: str,
        temperature: float,
        max_tokens: int,
        **kwargs: Any,
    ) -> Generator[str, None, None]:
        """Generate streaming response via server endpoint."""
        if not hasattr(self, '_client') or not self._client:
            raise RuntimeError("vLLM client not initialized")
        
        messages = [{"role": "user", "content": prompt}]
        
        stream = self._client.chat.completions.create(
            model=self.model_name,
            messages=messages,  # type: ignore
            temperature=temperature,
            max_tokens=max_tokens,
            stream=True,
        )
        
        for chunk in stream:
            if chunk.choices[0].delta.content:  # type: ignore
                yield chunk.choices[0].delta.content  # type: ignore
    
    def chat_completion(
        self,
        messages: List[Dict[str, str]],
        *,
        temperature: float = 0.1,
        max_tokens: int = 512,
        **kwargs: Any,
    ) -> Optional[str]:
        """Generate chat completion using vLLM."""
        if not self.is_available():
            if not self.initialize():
                logger.debug("vLLM provider not available for chat completion")
                return None
        
        try:
            # Use server endpoint if available
            if self.server_url and hasattr(self, '_client'):
                completion = self._client.chat.completions.create(
                    model=self.model_name,
                    messages=messages,  # type: ignore
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
                return completion.choices[0].message.content  # type: ignore[no-any-return]
            
            # For direct API, convert messages to prompt
            from joshu.tools.response_utils import format_messages_as_prompt
            prompt = format_messages_as_prompt(messages)
            return self._generate_via_direct_api(prompt, temperature, max_tokens, **kwargs)
            
        except Exception as e:
            logger.debug(f"vLLM chat completion failed: {e}")
            return None
    
    def cleanup(self) -> None:
        """Cleanup vLLM resources."""
        super().cleanup()
        self._llm = None
        if hasattr(self, '_client'):
            self._client = None

