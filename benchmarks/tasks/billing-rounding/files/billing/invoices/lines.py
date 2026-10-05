from dataclasses import dataclass

from billing.money.rounding import to_cents


@dataclass
class Line:
    description: str
    unit_price: float
    quantity: float = 1

    def net(self) -> float:
        return to_cents(self.unit_price * self.quantity)
