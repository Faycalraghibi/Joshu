"""Alert when the average gets too high."""

from metrics import stats


def too_slow(times, limit):
    return stats.mean(times) > limit
