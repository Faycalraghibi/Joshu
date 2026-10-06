import pytest
from limiter import TokenBucket


class Clock:
    def __init__(self):
        self.now = 100.0

    def __call__(self):
        return self.now


def make(capacity=3, rate=1.0):
    clock = Clock()
    return TokenBucket(capacity, rate, clock=clock), clock


def test_starts_full_and_drains():
    b, _ = make()
    assert b.available() == pytest.approx(3)
    assert [b.allow() for _ in range(4)] == [True, True, True, False]


def test_refills_continuously_up_to_capacity():
    b, clock = make(capacity=2, rate=0.5)
    assert b.allow(2)
    clock.now += 1
    assert b.available() == pytest.approx(0.5)
    assert not b.allow()
    clock.now += 1
    assert b.allow()
    clock.now += 100
    assert b.available() == pytest.approx(2)


def test_failed_allow_takes_nothing():
    b, clock = make(capacity=3, rate=1)
    assert b.allow(2)
    assert not b.allow(2)
    assert b.available() == pytest.approx(1)


def test_wait_time():
    b, clock = make(capacity=4, rate=2)
    assert b.wait_time() == 0.0
    assert b.allow(4)
    assert b.wait_time(1) == pytest.approx(0.5)
    assert b.wait_time(3) == pytest.approx(1.5)
    assert b.available() == pytest.approx(0)  # wait_time takes nothing
    clock.now += 0.5
    assert b.allow(1)


def test_validation():
    for capacity, rate in [(0, 1), (1, 0), (-1, 1), (1, -2)]:
        with pytest.raises(ValueError):
            TokenBucket(capacity, rate)
    b, _ = make(capacity=2)
    for cost in (0, -1, 3):
        with pytest.raises(ValueError):
            b.allow(cost)
        with pytest.raises(ValueError):
            b.wait_time(cost)
