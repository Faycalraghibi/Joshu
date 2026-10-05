from typing import Iterable

from timesheet.parse import parse_duration, parse_range


def worked(line: str) -> int:
    """'09:00-17:30 break 30m' -> minutes worked (range minus break)."""
    parts = line.split()
    minutes = parse_range(parts[0])
    if len(parts) == 3 and parts[1] == "break":
        minutes -= parse_duration(parts[2])
    return minutes


def total(lines: Iterable[str]) -> str:
    minutes = sum(worked(line) for line in lines if line.strip())
    return f"{minutes // 60}h{minutes % 60:02d}m"
