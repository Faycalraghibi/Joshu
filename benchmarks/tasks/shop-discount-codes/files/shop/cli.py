"""python -m shop.cli NAME:PRICE[:QTY] ..."""

import argparse
import sys
from decimal import Decimal

from shop.cart import Cart
from shop.models import Item
from shop.receipt import render


def parse_item(text: str) -> Item:
    parts = text.split(":")
    qty = int(parts[2]) if len(parts) > 2 else 1
    return Item(parts[0], Decimal(parts[1]), qty)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="shop")
    parser.add_argument("items", nargs="+")
    args = parser.parse_args(argv)
    cart = Cart()
    for text in args.items:
        cart.add(parse_item(text))
    print(render(cart))
    return 0


if __name__ == "__main__":
    sys.exit(main())
