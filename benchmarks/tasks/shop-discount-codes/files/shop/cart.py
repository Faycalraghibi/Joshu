from decimal import ROUND_HALF_UP, Decimal
from typing import List

from shop.models import Item

CENT = Decimal("0.01")


class Cart:
    def __init__(self) -> None:
        self.items: List[Item] = []

    def add(self, item: Item) -> None:
        self.items.append(item)

    def subtotal(self) -> Decimal:
        return sum((i.price * i.qty for i in self.items), Decimal("0"))

    def total(self) -> Decimal:
        return self.subtotal().quantize(CENT, rounding=ROUND_HALF_UP)
