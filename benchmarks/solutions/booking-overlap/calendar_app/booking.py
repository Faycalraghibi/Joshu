"""Accepting bookings without double-booking a room."""

from datetime import datetime, timedelta
from typing import List

from calendar_app.models import Booking


class ConflictError(Exception):
    pass


def overlaps(a: Booking, b: Booking) -> bool:
    """True when two bookings of the same room share any moment (ends are exclusive)."""
    return a.room == b.room and a.start < b.end and b.start < a.end


class Calendar:
    def __init__(self) -> None:
        self.bookings: List[Booking] = []

    def book(self, booking: Booking) -> None:
        for existing in self.bookings:
            if overlaps(existing, booking):
                raise ConflictError(f"{booking.room} is taken by {existing.title!r}")
        self.bookings.append(booking)

    def free_slots(
        self, room: str, day_start: datetime, day_end: datetime, length: timedelta
    ) -> List[datetime]:
        """
        Start times, every `length` from day_start, of slots of `length` that
        fit before day_end (inclusive: a slot may end exactly at day_end) and
        don't overlap a booking of the room.
        """
        slots = []
        start = day_start
        while start + length <= day_end:
            candidate = Booking(room, start, start + length)
            if not any(overlaps(candidate, b) for b in self.bookings):
                slots.append(start)
            start += length
        return slots
