from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict


class LLM(ABC):
    @abstractmethod
    def generate(self, prompt: str, **kwargs: Any) -> str:
        raise NotImplementedError


