import pytest

from cache import TTLCache


class Clock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now


def make(n=2, ttl=10):
    clock = Clock()
    return TTLCache(n, ttl, clock=clock), clock


def test_basic():
    c, _ = make()
    c.set("a", 1)
    assert c.get("a") == 1 and "a" in c and len(c) == 1
    assert c.get("zz", "d") == "d"


def test_invalid():
    with pytest.raises(ValueError):
        TTLCache(0, 1)
    with pytest.raises(ValueError):
        TTLCache(1, 0)


def test_expiry_from_set_not_get():
    c, clock = make(ttl=10)
    c.set("a", 1)
    clock.now = 9
    assert c.get("a") == 1
    clock.now = 10
    assert c.get("a") is None and "a" not in c and len(c) == 0


def test_set_restarts_ttl():
    c, clock = make(ttl=10)
    c.set("a", 1)
    clock.now = 8
    c.set("a", 2)
    clock.now = 15
    assert c.get("a") == 2


def test_lru_eviction_counts_gets():
    c, _ = make(n=2)
    c.set("a", 1)
    c.set("b", 2)
    c.get("a")
    c.set("c", 3)
    assert "b" not in c and c.get("a") == 1 and c.get("c") == 3


def test_expired_dropped_before_evicting():
    c, clock = make(n=2, ttl=10)
    c.set("a", 1)
    clock.now = 5
    c.set("b", 2)
    clock.now = 11  # a expired, b alive
    c.set("c", 3)
    assert c.get("b") == 2 and c.get("c") == 3 and len(c) == 2


def test_update_makes_most_recent():
    c, _ = make(n=2)
    c.set("a", 1)
    c.set("b", 2)
    c.set("a", 10)
    c.set("c", 3)
    assert "b" not in c and c.get("a") == 10


def test_delete():
    c, clock = make(ttl=10)
    c.set("a", 1)
    assert c.delete("a") is True and c.delete("a") is False
    c.set("b", 1)
    clock.now = 20
    assert c.delete("b") is False


def test_miss_is_not_a_use():
    c, _ = make(n=2)
    c.set("a", 1)
    c.set("b", 2)
    c.get("missing")
    c.set("c", 3)
    assert "a" not in c and "b" in c
