"""Weekly usage reports."""

from collections import defaultdict
from typing import Dict, Iterable

from calendar_app.models import Booking


def hours_by_room(bookings: Iterable[Booking]) -> Dict[str, float]:
    """Total booked hours per room."""
    totals: Dict[str, float] = defaultdict(float)
    for booking in bookings:
        totals[booking.room] += (booking.end - booking.start).total_seconds() / 3600
    return dict(totals)
