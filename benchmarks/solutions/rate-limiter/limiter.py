"""A token-bucket rate limiter."""

import time
from typing import Callable


class TokenBucket:
    """
    Allows bursts of up to `capacity` actions, refilled at `rate` tokens per second.

    - capacity and rate must be > 0, else ValueError.
    - The bucket starts full.
    - Tokens refill continuously (fractions accumulate) and never exceed capacity.
    - allow(cost=1): if at least `cost` tokens are available, take them and
      return True; otherwise take nothing and return False. cost must be > 0
      and <= capacity, else ValueError.
    - wait_time(cost=1): seconds until allow(cost) would succeed (0.0 if it
      would now); takes nothing. Same cost rules as allow.
    - available(): the tokens available now (a float).
    - clock: returns the current time in seconds (default time.monotonic).
    """

    def __init__(self, capacity: float, rate: float, clock: Callable[[], float] = time.monotonic):
        if capacity <= 0 or rate <= 0:
            raise ValueError("capacity and rate must be > 0")
        self.capacity = float(capacity)
        self.rate = float(rate)
        self.clock = clock
        self._tokens = float(capacity)
        self._last = clock()

    def _refill(self) -> None:
        now = self.clock()
        self._tokens = min(self.capacity, self._tokens + (now - self._last) * self.rate)
        self._last = now

    def _check(self, cost: float) -> None:
        if cost <= 0 or cost > self.capacity:
            raise ValueError("cost must be > 0 and <= capacity")

    def available(self) -> float:
        self._refill()
        return self._tokens

    def allow(self, cost: float = 1) -> bool:
        self._check(cost)
        self._refill()
        if self._tokens >= cost:
            self._tokens -= cost
            return True
        return False

    def wait_time(self, cost: float = 1) -> float:
        self._check(cost)
        self._refill()
        missing = cost - self._tokens
        return 0.0 if missing <= 0 else missing / self.rate
