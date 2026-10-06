"""Bookings of rooms."""

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class Booking:
    room: str
    start: datetime
    end: datetime  # exclusive: a booking ending at 10:00 leaves 10:00 free
    title: str = ""

    def __post_init__(self):
        if self.end <= self.start:
            raise ValueError("a booking must end after it starts")
