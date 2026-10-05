import re

_DURATION = re.compile(r"^(?:(\d+)h)?(?:(\d+)m)?$")


def parse_duration(text: str) -> int:
    """'1h30m' -> 90, '45m' -> 45, '2h' -> 120 (minutes)."""
    match = _DURATION.match(text.strip())
    if not match or not text.strip():
        raise ValueError(f"bad duration: {text!r}")
    hours, minutes = match.groups()
    return int(hours or 0) * 60 + int(minutes or 0)


def to_minutes(clock: str) -> int:
    hours, minutes = clock.split(":")
    return int(hours) * 60 + int(minutes)


def parse_range(text: str) -> int:
    """'09:00-17:30' -> minutes worked between the two times."""
    start, end = text.split("-")
    return (to_minutes(end) - to_minutes(start)) % (24 * 60)
