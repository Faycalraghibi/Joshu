from __future__ import annotations

from typing import Dict

from .local_models import EchoModel
from .llm_interface import LLM
from .llama_cpp_loader import maybe_load_llama_from_env


def get_model(model_name: str) -> LLM:
    llama = maybe_load_llama_from_env()
    if llama is not None:
        # Adapt to LLM interface with a lightweight wrapper
        class _Adapter(LLM):
            def generate(self, prompt: str, **kwargs):
                return llama.generate(prompt, **kwargs)

        return _Adapter()
    return EchoModel()


