"""Basic statistics."""

import warnings
from typing import Sequence


def mean(values: Sequence[float]) -> float:
    """The arithmetic mean; ValueError for no values."""
    if not values:
        raise ValueError("no values")
    return sum(values) / len(values)


def calc_avg(values: Sequence[float]) -> float:
    """Deprecated: use mean()."""
    warnings.warn("calc_avg() is deprecated; use mean()", DeprecationWarning, stacklevel=2)
    return mean(values)


def spread(values: Sequence[float]) -> float:
    """Largest minus smallest."""
    return max(values) - min(values)
