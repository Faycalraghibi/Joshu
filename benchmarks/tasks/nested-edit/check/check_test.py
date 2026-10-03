import pytest
from inventory import Inventory


def test_remove():
    inv = Inventory()
    inv.add("apple", 3)
    inv.remove("apple", 2)
    assert inv.stock == {"apple": 1}
    inv.remove("apple", 1)
    assert inv.stock == {}


def test_not_enough_stock():
    inv = Inventory()
    inv.add("apple", 1)
    with pytest.raises(ValueError, match="not enough stock"):
        inv.remove("apple", 2)
    assert inv.stock == {"apple": 1}
    with pytest.raises(ValueError, match="not enough stock"):
        inv.remove("pear", 1)
