from typing import Iterable

from billing.invoices.invoice import Invoice
from billing.money.rounding import to_cents


def revenue(invoices: Iterable[Invoice]) -> float:
    return to_cents(sum(i.total() for i in invoices))
