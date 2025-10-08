from __future__ import annotations

from typing import Any

from .llm_interface import LLM


class EchoModel(LLM):
    def generate(self, prompt: str, **kwargs: Any) -> str:
        return f"Echo: {prompt}"


