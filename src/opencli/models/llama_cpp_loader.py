from __future__ import annotations

import os
from typing import Any

try:
    from llama_cpp import Llama  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    Llama = None  # type: ignore


class LlamaCppWrapper:
    def __init__(self, model_path: str, n_ctx: int = 4096, n_threads: int | None = None) -> None:
        if Llama is None:
            raise RuntimeError("llama-cpp-python is not installed")
        self._llm = Llama(model_path=model_path, n_ctx=n_ctx, n_threads=n_threads)

    def generate(self, prompt: str, max_tokens: int = 256, temperature: float = 0.1) -> str:
        output = self._llm(
            prompt,
            max_tokens=max_tokens,
            temperature=temperature,
            stop=["</s>", "</assistant>", "</user>"],
        )
        text = output.get("choices", [{}])[0].get("text", "")
        return text.strip()


def maybe_load_llama_from_env() -> LlamaCppWrapper | None:
    model_path = os.getenv("OPENCLI_LLAMA_CPP_MODEL")
    if not model_path:
        return None
    try:
        return LlamaCppWrapper(model_path)
    except Exception:
        return None


