from decimal import Decimal

from shop.cart import Cart
from shop.models import Item
from shop.receipt import render


def test_total():
    cart = Cart()
    cart.add(Item("pen", Decimal("1.50"), 2))
    cart.add(Item("pad", Decimal("4.00")))
    assert cart.total() == Decimal("7.00")


def test_receipt():
    cart = Cart()
    cart.add(Item("pen", Decimal("1.50"), 2))
    assert render(cart).splitlines()[-1] == "Total: 3.00"
