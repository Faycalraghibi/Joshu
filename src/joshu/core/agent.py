from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict


@dataclass
class AgentResponse:
    text: str
    metadata: Dict[str, Any]


class Agent:
    """Main assistant logic placeholder.

    This will orchestrate model calls, tools, RAG, and memory.
    """

    def __init__(self) -> None:
        pass

    def run(self, prompt: str) -> AgentResponse:
        return AgentResponse(text="Not implemented", metadata={})
