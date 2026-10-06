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
        raise NotImplementedError

    def available(self) -> float:
        raise NotImplementedError

    def allow(self, cost: float = 1) -> bool:
        raise NotImplementedError

    def wait_time(self, cost: float = 1) -> float:
        raise NotImplementedError
