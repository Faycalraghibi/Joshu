import subprocess
import sys
from decimal import Decimal

import pytest
from shop.cart import Cart
from shop.codes import CODES
from shop.models import Item
from shop.receipt import render


def cart_of(*prices):
    cart = Cart()
    for p in prices:
        cart.add(Item("x", Decimal(p)))
    return cart


def test_codes_module():
    assert CODES["SAVE10"] == 10 and CODES["HALF"] == 50


def test_discount_and_total():
    cart = cart_of("10.00")
    cart.apply_code("SAVE10")
    assert cart.discount() == Decimal("1.00")
    assert cart.total() == Decimal("9.00")


def test_case_insensitive_and_unknown():
    cart = cart_of("10.00")
    cart.apply_code("half")
    assert cart.total() == Decimal("5.00")
    with pytest.raises(ValueError):
        cart.apply_code("NOPE")


def test_half_up_rounding():
    cart = cart_of("0.05")
    cart.apply_code("SAVE10")
    assert cart.discount() == Decimal("0.01")
    assert cart.total() == Decimal("0.04")


def test_no_code_unchanged():
    cart = cart_of("2.00")
    assert cart.discount() == Decimal("0.00") or cart.discount() == 0
    assert cart.total() == Decimal("2.00")
    assert "Discount" not in render(cart)


def test_receipt_line_before_total():
    cart = cart_of("10.00")
    cart.apply_code("SAVE10")
    lines = render(cart).splitlines()
    assert lines[-2] == "Discount (SAVE10): -1.00"
    assert lines[-1] == "Total: 9.00"


def test_cli():
    out = subprocess.run(
        [sys.executable, "-m", "shop.cli", "pen:10.00", "--code", "SAVE10"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    assert "Discount (SAVE10): -1.00" in out and "Total: 9.00" in out


def test_existing_behaviour():
    cart = Cart()
    cart.add(Item("pen", Decimal("1.50"), 2))
    cart.add(Item("pad", Decimal("4.00")))
    assert cart.total() == Decimal("7.00")
