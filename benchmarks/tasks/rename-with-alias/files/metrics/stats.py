"""Basic statistics."""

from typing import Sequence


def calc_avg(values: Sequence[float]) -> float:
    """The arithmetic mean; ValueError for no values."""
    if not values:
        raise ValueError("no values")
    return sum(values) / len(values)


def spread(values: Sequence[float]) -> float:
    """Largest minus smallest."""
    return max(values) - min(values)
