from timesheet.parse import parse_duration, parse_range
from timesheet.summary import total


def test_duration():
    assert parse_duration("1h30m") == 90
    assert parse_duration("45m") == 45


def test_range():
    assert parse_range("09:00-17:30") == 510


def test_total():
    assert total(["09:00-17:30 break 1h15m", "10:00-12:00"]) == "9h15m"
