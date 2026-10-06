"""Rounding helpers used for every amount shown to customers."""


def to_cents(amount: float) -> float:
    """Round an amount to cents."""
    return round(amount, 2)


def split_evenly(amount: float, parts: int) -> list:
    share = to_cents(amount / parts)
    shares = [share] * parts
    shares[-1] = to_cents(amount - share * (parts - 1))
    return shares
