"""Retrying flaky calls."""

import time
from typing import Callable, Tuple, Type


def retry(
    times: int,
    exceptions: Tuple[Type[BaseException], ...] = (Exception,),
    backoff: float = 0.0,
    sleep: Callable[[float], None] = time.sleep,
):
    """
    Decorator: call the function up to `times` times while it raises one of
    `exceptions`.

    - times must be >= 1, backoff >= 0, else ValueError (when retry() is called).
    - Before attempt n (n >= 2), sleep(backoff * 2 ** (n - 2)) is called:
      backoff, 2*backoff, 4*backoff, ... (not at all when backoff is 0).
    - An exception not in `exceptions` propagates at once, without retrying.
    - When every attempt fails, the last exception is raised.
    - The wrapper keeps the function's __name__ and __doc__ and has an
      `attempts` attribute: how many attempts its latest call made.
    """
    raise NotImplementedError
