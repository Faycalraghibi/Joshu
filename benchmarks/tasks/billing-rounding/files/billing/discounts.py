from billing.money.rounding import to_cents


def percent_off(amount: float, percent: float) -> float:
    return to_cents(amount * (100 - percent) / 100)
