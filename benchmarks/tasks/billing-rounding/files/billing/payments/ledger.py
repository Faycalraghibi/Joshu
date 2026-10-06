from typing import List, Tuple

_ENTRIES: List[Tuple[str, float]] = []


def record(invoice_number: str, amount: float) -> None:
    _ENTRIES.append((invoice_number, amount))


def balance(invoice_number: str) -> float:
    return sum(a for n, a in _ENTRIES if n == invoice_number)
