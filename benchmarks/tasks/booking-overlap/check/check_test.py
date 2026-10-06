from datetime import datetime, timedelta

import pytest
from calendar_app.booking import Calendar, ConflictError, overlaps
from calendar_app.models import Booking
from calendar_app.report import hours_by_room


def at(hour, minute=0, day=6):
    return datetime(2026, 10, day, hour, minute)


def test_back_to_back_is_fine_but_overlap_is_not():
    cal = Calendar()
    cal.book(Booking("A", at(9), at(10), "standup"))
    cal.book(Booking("A", at(10), at(11), "review"))
    cal.book(Booking("B", at(9, 30), at(10, 30), "other room"))
    with pytest.raises(ConflictError):
        cal.book(Booking("A", at(10, 59), at(12)))
    with pytest.raises(ConflictError):
        cal.book(Booking("A", at(8), at(12)))  # contains both
    assert not overlaps(Booking("A", at(9), at(10)), Booking("A", at(10), at(11)))


def test_hours_for_long_bookings():
    bookings = [
        Booking("A", at(9), at(11)),
        Booking("A", at(9, day=7), at(9, day=9)),  # 48 hours
        Booking("B", at(9), at(9, 30)),
    ]
    assert hours_by_room(bookings) == {"A": 50.0, "B": 0.5}


def test_free_slots_include_the_last_one():
    cal = Calendar()
    cal.book(Booking("A", at(10), at(11)))
    slots = cal.free_slots("A", at(9), at(12), timedelta(hours=1))
    assert slots == [at(9), at(11)]
    assert cal.free_slots("B", at(9), at(10), timedelta(minutes=30)) == [at(9), at(9, 30)]
