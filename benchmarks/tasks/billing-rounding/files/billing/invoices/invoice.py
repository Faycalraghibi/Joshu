from dataclasses import dataclass, field
from typing import List

from billing.invoices.lines import Line
from billing.money.rounding import to_cents
from billing.tax.vat import vat


@dataclass
class Invoice:
    number: str
    lines: List[Line] = field(default_factory=list)
    vat_kind: str = "standard"

    def net(self) -> float:
        return to_cents(sum(line.net() for line in self.lines))

    def tax(self) -> float:
        return vat(self.net(), self.vat_kind)

    def total(self) -> float:
        return to_cents(self.net() + self.tax())
