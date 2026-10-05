from billing.money.rounding import split_evenly


def installments(total: float, months: int) -> list:
    return split_evenly(total, months)
