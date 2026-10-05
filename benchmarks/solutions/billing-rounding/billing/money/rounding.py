"""Rounding helpers used for every amount shown to customers."""

from decimal import ROUND_HALF_UP, Decimal

CENT = Decimal("0.01")


def _cents(amount: float) -> Decimal:
    # repr() gives the shortest decimal for the float (2.675 -> "2.675"),
    # so halves round up instead of falling on the float's binary error
    return Decimal(repr(amount)).quantize(CENT, rounding=ROUND_HALF_UP)


def to_cents(amount: float) -> float:
    """Round an amount to cents, halves away from zero."""
    return float(_cents(amount))


def split_evenly(amount: float, parts: int) -> list:
    """Split into `parts` cent amounts that add up exactly to the rounded total."""
    total = _cents(amount)
    share = (total / parts).quantize(CENT, rounding=ROUND_HALF_UP)
    shares = [share] * parts
    shares[-1] = total - share * (parts - 1)
    return [float(s) for s in shares]
