from dataclasses import dataclass


@dataclass
class Customer:
    id: int
    name: str
    country: str = "FR"
    vat_kind: str = "standard"
