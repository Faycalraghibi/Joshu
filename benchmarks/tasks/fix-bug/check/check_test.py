from calc import add, average


def test_add():
    assert add(2, 3) == 5
    assert add(-1, 1) == 0


def test_average():
    assert average([2, 4]) == 3
    assert average([5]) == 5
