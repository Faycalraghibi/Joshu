"""A size-bounded cache whose entries also expire."""

import time
from typing import Any, Callable, Hashable


class TTLCache:
    """
    At most `max_items` live entries; each expires `ttl` seconds after
    it was last *set* (reading does not extend its life).

    - An expired entry behaves as if absent: `get` returns the default,
      `in` is False, and it does not count in `len`.
    - `set` on a full cache first drops expired entries; if it is
      still full, it evicts the least recently *used* entry, where
      both `get` (a hit) and `set` count as a use.
    - `set` on an existing key replaces the value, restarts its ttl
      and makes it the most recently used.
    - `clock` returns the current time in seconds (default
      time.monotonic); tests pass a fake clock.
    """

    def __init__(
        self, max_items: int, ttl: float, clock: Callable[[], float] = time.monotonic
    ) -> None:
        if max_items < 1 or ttl <= 0:
            raise ValueError("max_items must be >= 1 and ttl > 0")
        raise NotImplementedError

    def get(self, key: Hashable, default: Any = None) -> Any:
        raise NotImplementedError

    def set(self, key: Hashable, value: Any) -> None:
        raise NotImplementedError

    def delete(self, key: Hashable) -> bool:
        """Remove `key`; True if a live entry was removed."""
        raise NotImplementedError

    def __contains__(self, key: Hashable) -> bool:
        raise NotImplementedError

    def __len__(self) -> int:
        raise NotImplementedError
