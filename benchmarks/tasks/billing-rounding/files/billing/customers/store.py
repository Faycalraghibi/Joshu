from typing import Dict

from billing.customers.models import Customer

_CUSTOMERS: Dict[int, Customer] = {}


def add(customer: Customer) -> None:
    _CUSTOMERS[customer.id] = customer


def get(customer_id: int) -> Customer:
    return _CUSTOMERS[customer_id]
