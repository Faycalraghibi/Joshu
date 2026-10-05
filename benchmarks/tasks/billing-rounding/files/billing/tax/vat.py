from billing.money.rounding import to_cents
from billing.tax.rates import rate


def vat(net: float, kind: str = "standard") -> float:
    return to_cents(net * rate(kind))
