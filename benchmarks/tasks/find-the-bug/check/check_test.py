from shop.cart import total
from shop.pricing import discount_rate


def test_totals():
    assert total([(20.0, 2), (5.0, 1)]) == 45.0
    assert total([(20.0, 2), (5.0, 1)], code="SAVE10") == 40.5
    assert total([(10.0, 1)], code="HALF") == 5.0
    assert total([(10.0, 1)], code="NOPE") == 10.0


def test_rate_is_a_fraction():
    assert discount_rate("SAVE10") == 0.1
