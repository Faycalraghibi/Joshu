"""A size-bounded cache whose entries also expire."""

import time
from collections import OrderedDict
from typing import Any, Callable, Hashable


class TTLCache:
    def __init__(
        self, max_items: int, ttl: float, clock: Callable[[], float] = time.monotonic
    ) -> None:
        if max_items < 1 or ttl <= 0:
            raise ValueError("max_items must be >= 1 and ttl > 0")
        self.max_items = max_items
        self.ttl = ttl
        self.clock = clock
        self._data = OrderedDict()  # key -> (value, expires_at)

    def _alive(self, key) -> bool:
        entry = self._data.get(key)
        if entry is None:
            return False
        if self.clock() >= entry[1]:
            del self._data[key]
            return False
        return True

    def _purge(self) -> None:
        now = self.clock()
        for key in [k for k, (_, exp) in self._data.items() if now >= exp]:
            del self._data[key]

    def get(self, key: Hashable, default: Any = None) -> Any:
        if not self._alive(key):
            return default
        self._data.move_to_end(key)
        return self._data[key][0]

    def set(self, key: Hashable, value: Any) -> None:
        if key in self._data:
            del self._data[key]
        elif len(self._data) >= self.max_items:
            self._purge()
            if len(self._data) >= self.max_items:
                self._data.popitem(last=False)
        self._data[key] = (value, self.clock() + self.ttl)

    def delete(self, key: Hashable) -> bool:
        if not self._alive(key):
            return False
        del self._data[key]
        return True

    def __contains__(self, key: Hashable) -> bool:
        return self._alive(key)

    def __len__(self) -> int:
        self._purge()
        return len(self._data)
