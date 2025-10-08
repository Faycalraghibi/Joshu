from __future__ import annotations

from typing import Any, Dict, List


class ConversationContext:
    def __init__(self) -> None:
        self.messages: List[Dict[str, Any]] = []

    def add(self, role: str, content: str) -> None:
        self.messages.append({"role": role, "content": content})

    def as_list(self) -> List[Dict[str, Any]]:
        return list(self.messages)


