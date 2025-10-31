from __future__ import annotations

import os
from typing import Any, Generator

try:
    from llama_cpp import Llama  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    Llama = None  # type: ignore


class LlamaCppWrapper:
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


def maybe_load_llama_from_env() -> LlamaCppWrapper | None:
    model_path = os.getenv("JOSHU_LLAMA_CPP_MODEL")
    if not model_path:
        return None
    try:
        # Get additional configuration from environment variables
        n_ctx = int(os.getenv("JOSHU_LLAMA_CTX_SIZE", "4096"))
        n_threads = int(os.getenv("JOSHU_LLAMA_THREADS", "0")) or None
        n_gpu_layers = int(os.getenv("JOSHU_LLAMA_GPU_LAYERS", "0"))
        seed = int(os.getenv("JOSHU_LLAMA_SEED", "42"))
        
        return LlamaCppWrapper(model_path, n_ctx, n_threads, n_gpu_layers, seed)
    except Exception:
        return None
