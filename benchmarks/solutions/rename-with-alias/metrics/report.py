"""Summaries of response times."""

from metrics.stats import mean, spread


def summary(times):
    return {"avg": round(mean(times), 2), "spread": spread(times)}
