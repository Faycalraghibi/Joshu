from billing.money.currency import symbol
from billing.money.rounding import to_cents


def money(amount: float, currency: str = "EUR") -> str:
    return f"{symbol(currency)}{to_cents(amount):,.2f}"
