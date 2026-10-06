"""Summaries of response times."""

from metrics.stats import calc_avg, spread


def summary(times):
    return {"avg": round(calc_avg(times), 2), "spread": spread(times)}
