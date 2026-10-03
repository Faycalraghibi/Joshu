from pagination import page_count, paginate

ITEMS = list(range(10))


def test_pages():
    assert paginate(ITEMS, 1, 3) == [0, 1, 2]
    assert paginate(ITEMS, 2, 3) == [3, 4, 5]
    assert paginate(ITEMS, 4, 3) == [9]


def test_page_count():
    assert page_count(ITEMS, 3) == 4
    assert page_count(ITEMS, 5) == 2
    assert page_count([], 5) == 0
