import pytest
from timesheet.parse import parse_duration, parse_range
from timesheet.summary import total, worked


@pytest.mark.parametrize(
    "text, minutes",
    [
        ("1h30m", 90),
        ("45m", 45),
        ("2h", 120),
        ("0h5m", 5),
        ("10h0m", 600),
    ],
)
def test_durations(text, minutes):
    assert parse_duration(text) == minutes


@pytest.mark.parametrize("text", ["", "abc", "5", "h", "1x"])
def test_bad_durations(text):
    with pytest.raises(ValueError):
        parse_duration(text)


def test_overnight():
    assert parse_range("22:00-06:00") == 480
    assert parse_range("23:30-00:15") == 45
    assert worked("22:00-06:00 break 30m") == 450


def test_totals():
    assert total(["09:00-17:30 break 1h15m", "10:00-12:00"]) == "9h15m"
    assert total(["22:00-06:00", "", "08:00-08:45"]) == "8h45m"
