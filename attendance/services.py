"""Attendance rules: RFID scans, automatic absentees and staff lists."""
from datetime import datetime, timedelta

from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone

from students.models import Student

from .models import Holiday, Status, StudentAttendance

# A second scan within this window is treated as an accidental double tap.
DOUBLE_SCAN_SECONDS = 60
# Scans this long before a batch starts / after it ends are still "in shift".
SHIFT_GRACE = timedelta(minutes=60)


def staff_queryset():
    User = get_user_model()
    return User.objects.filter(is_active=True, role__in=[User.Role.ADMIN, User.Role.FACULTY], is_superuser=False).order_by("username")


def is_holiday(day):
    return Holiday.objects.filter(date=day).exists()


def _outside_shift(student, moment):
    program = student.program
    if not program or not program.start_time or not program.end_time:
        return False
    local = timezone.localtime(moment)
    tz = local.tzinfo
    start = datetime.combine(local.date(), program.start_time, tzinfo=tz) - SHIFT_GRACE
    end = datetime.combine(local.date(), program.end_time, tzinfo=tz) + SHIFT_GRACE
    return not (start <= local <= end)


def process_scan(card, now=None):
    """Handle one RFID card scan. Returns {"ok", "level", "message", "student"} for the scan screen."""
    now = now or timezone.now()
    card = (card or "").strip()
    if not card:
        return {"ok": False, "level": "error", "message": "No card number received.", "student": None}
    student = Student.objects.select_related("program").filter(rfid_uid__iexact=card).first()
    if student is None:
        return {"ok": False, "level": "error", "message": "Unknown card. It is not linked to any student.", "student": None}
    name = f"{student.first_name} {student.last_name}".strip()
    info = {"student": {"id": student.student_id, "name": name, "batch": student.program.name if student.program else "",
                        "seat": student.seat_number}}
    if student.status == Student.Status.DEACTIVATED:
        return {"ok": False, "level": "error", "message": "This card is disabled permanently (student deactivated).", **info}
    plan_over = student.subscription_end is not None and student.subscription_end < now
    if student.status == Student.Status.INACTIVE or plan_over:
        return {"ok": False, "level": "warn", "message": "Plan expired. Please pay the monthly fee to use the library.", **info}

    today = timezone.localdate(now)
    with transaction.atomic():
        record, created = StudentAttendance.objects.select_for_update().get_or_create(
            student=student, date=today,
            defaults={"status": Status.PRESENT, "check_in": now, "source": StudentAttendance.Source.RFID,
                      "outside_shift": _outside_shift(student, now)},
        )
        if created:
            msg = f"Welcome, {name}. Seat {student.seat_number or '-'}."
            if record.outside_shift:
                msg += " (Outside your batch timings.)"
            return {"ok": True, "level": "ok" if not record.outside_shift else "warn", "message": msg, **info}
        if record.status != Status.PRESENT or not record.check_in:
            # Marked Absent/Leave earlier today, but the student is here after all.
            record.status = Status.PRESENT
            record.check_in = now
            record.check_out = None
            record.source = StudentAttendance.Source.RFID
            record.outside_shift = _outside_shift(student, now)
            record.save()
            return {"ok": True, "level": "ok", "message": f"Welcome, {name}. Attendance corrected to Present.", **info}
        last = record.check_out or record.check_in
        if (now - last).total_seconds() < DOUBLE_SCAN_SECONDS:
            return {"ok": True, "level": "info", "message": f"{name}: already scanned a moment ago.", **info}
        record.check_out = now
        record.save(update_fields=["check_out", "updated_at"])
        return {"ok": True, "level": "ok", "message": f"Goodbye, {name}. Exit time recorded.", **info}


def mark_absentees(day, batch=None):
    """Mark every active student with no record for `day` as Absent (skipped on holidays).

    Returns the number of students marked, or None when `day` is a holiday.
    """
    if is_holiday(day):
        return None
    students = Student.objects.filter(status=Student.Status.ACTIVE, enrollment_date__lte=day)
    if batch:
        students = students.filter(program=batch)
    marked = set(StudentAttendance.objects.filter(date=day).values_list("student_id", flat=True))
    new = [
        StudentAttendance(student=s, date=day, status=Status.ABSENT, source=StudentAttendance.Source.AUTO)
        for s in students if s.pk not in marked
    ]
    StudentAttendance.objects.bulk_create(new, ignore_conflicts=True)
    return len(new)
