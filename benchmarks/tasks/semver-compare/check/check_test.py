import pytest
from semver import Version, compare, latest, parse

ORDER = [
    "1.0.0-alpha",
    "1.0.0-alpha.1",
    "1.0.0-alpha.beta",
    "1.0.0-beta",
    "1.0.0-beta.2",
    "1.0.0-beta.11",
    "1.0.0-rc.1",
    "1.0.0",
    "1.0.1",
    "1.1.0",
    "2.0.0-0",
    "2.0.0",
    "10.0.0",
]


def test_parse():
    assert parse("1.2.3") == Version(1, 2, 3)
    assert parse("1.0.0-rc.1+build.5") == Version(1, 0, 0, ("rc", "1"), ("build", "5"))
    assert parse("0.0.0+001") == Version(0, 0, 0, (), ("001",))


@pytest.mark.parametrize(
    "bad",
    [
        "1.2",
        "1.2.3.4",
        "01.2.3",
        "1.02.3",
        "v1.2.3",
        " 1.2.3",
        "1.2.3-",
        "1.2.3-a..b",
        "1.2.3-01",
        "1.2.3+",
        "1.2.3-a_b",
        "",
        "a.b.c",
        "1.2.-3",
    ],
)
def test_invalid(bad):
    with pytest.raises(ValueError):
        parse(bad)


def test_order():
    for low, high in zip(ORDER, ORDER[1:]):
        assert compare(low, high) == -1, (low, high)
        assert compare(high, low) == 1, (high, low)


def test_equal_and_build_ignored():
    assert compare("1.0.0+a", "1.0.0+b") == 0
    assert compare("1.0.0-rc.1+x", "1.0.0-rc.1") == 0


def test_latest():
    assert latest(["1.0.0", "1.0.0-rc.1", "0.9.9", "1.0.0-rc.2"]) == "1.0.0"
    assert latest(reversed(ORDER)) == "10.0.0"
    with pytest.raises(ValueError):
        latest([])
    with pytest.raises(ValueError):
        latest(["1.0.0", "nope"])
