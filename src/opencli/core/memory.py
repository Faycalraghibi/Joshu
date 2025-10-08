from __future__ import annotations

from typing import Dict, Optional


class MemoryStore:
    def __init__(self) -> None:
        self.kv: Dict[str, str] = {}

    def get(self, key: str) -> Optional[str]:
        return self.kv.get(key)

    def set(self, key: str, value: str) -> None:
        self.kv[key] = value


