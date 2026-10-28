"""Seat allocation for the library.

Rules
-----
* Seats are numbered 1..settings.TOTAL_SEATS and there is no reserve: every seat is usable.
* A Sankalp (full-day) student needs a seat to themselves.
* A morning (Pratibha) and an afternoon (Pragati) student can share one seat, because
  their timings do not overlap. Two students of the same shift never share.
* A student keeps the same seat every day until an admin changes it, the batch
  changes and the seat no longer fits, or the student is deactivated.
* A deactivated student's seat is released immediately.
"""
from django.conf import settings
from django.db import transaction

MORNING, AFTERNOON, FULL = "morning", "afternoon", "full_day"


def total_seats() -> int:
    return int(getattr(settings, "TOTAL_SEATS", 80))


def shifts_conflict(a: str, b: str) -> bool:
    """True when two shifts overlap in time (so they cannot share a seat)."""
    if FULL in (a, b):
        return True
    return a == b


def _holders(exclude_pk=None):
    """Map seat number -> list of shifts held, for students who currently hold a seat."""
    from .models import Student

    qs = Student.objects.filter(seat_number__isnull=False).exclude(status=Student.Status.DEACTIVATED)
    if exclude_pk:
        qs = qs.exclude(pk=exclude_pk)
    held = {}
    for seat, shift in qs.values_list("seat_number", "seat_shift"):
        held.setdefault(seat, []).append(shift)
    return held


def seat_is_free(seat: int, shift: str, exclude_pk=None) -> bool:
    if not 1 <= seat <= total_seats():
        return False
    return all(not shifts_conflict(shift, other) for other in _holders(exclude_pk).get(seat, []))


def free_seats(shift: str, exclude_pk=None):
    held = _holders(exclude_pk)
    return [
        seat for seat in range(1, total_seats() + 1)
        if all(not shifts_conflict(shift, other) for other in held.get(seat, []))
    ]


def pick_seat(shift: str, exclude_pk=None):
    """Best automatic seat for a shift, or None when the library is full for that shift.

    Morning/afternoon students go first to a seat already holding the other half-day
    shift (keeping fully empty seats free for full-day students); otherwise to the
    lowest empty seat. Full-day students always take the lowest completely empty seat.
    """
    held = _holders(exclude_pk)
    free = [
        seat for seat in range(1, total_seats() + 1)
        if all(not shifts_conflict(shift, other) for other in held.get(seat, []))
    ]
    if not free:
        return None
    if shift != FULL:
        pairing = [seat for seat in free if held.get(seat)]
        if pairing:
            return pairing[0]
    return free[0]


def lock_seat_rows():
    """Serialise seat changes (row locks on Postgres; harmless on SQLite)."""
    from .models import Student

    list(Student.objects.select_for_update().filter(seat_number__isnull=False).values_list("pk", flat=True))


def seat_map():
    """Full seat chart: list of dicts {seat, morning, afternoon, full} with Student objects."""
    from .models import Student

    rows = {n: {"seat": n, "morning": None, "afternoon": None, "full": None} for n in range(1, total_seats() + 1)}
    qs = (
        Student.objects.filter(seat_number__isnull=False)
        .exclude(status=Student.Status.DEACTIVATED)
        .select_related("program")
    )
    for st in qs:
        slot = {MORNING: "morning", AFTERNOON: "afternoon", FULL: "full"}[st.seat_shift]
        if st.seat_number in rows:
            rows[st.seat_number][slot] = st
    return list(rows.values())
