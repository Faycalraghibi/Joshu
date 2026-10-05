from decimal import ROUND_HALF_UP, Decimal
from typing import List, Optional

from shop.codes import CODES
from shop.models import Item

CENT = Decimal("0.01")


class Cart:
    def __init__(self) -> None:
        self.items: List[Item] = []
        self.code: Optional[str] = None

    def add(self, item: Item) -> None:
        self.items.append(item)

    def apply_code(self, code: str) -> None:
        code = code.upper()
        if code not in CODES:
            raise ValueError(f"unknown code: {code}")
        self.code = code

    def subtotal(self) -> Decimal:
        return sum((i.price * i.qty for i in self.items), Decimal("0"))

    def discount(self) -> Decimal:
        if not self.code:
            return Decimal("0.00")
        amount = self.subtotal() * Decimal(CODES[self.code]) / Decimal(100)
        return amount.quantize(CENT, rounding=ROUND_HALF_UP)

    def total(self) -> Decimal:
        return (self.subtotal() - self.discount()).quantize(CENT, rounding=ROUND_HALF_UP)
