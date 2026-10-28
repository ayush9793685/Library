from django.conf import settings
from django.db import models


class Status(models.TextChoices):
    PRESENT = "present", "Present"
    ABSENT = "absent", "Absent"
    LEAVE = "leave", "Leave"


class Holiday(models.Model):
    """Closed days: nobody is marked Absent automatically on these dates."""

    date = models.DateField(unique=True)
    name = models.CharField(max_length=120)

    class Meta:
        ordering = ["-date"]

    def __str__(self):
        return f"{self.date} {self.name}"


class StudentAttendance(models.Model):
    class Source(models.TextChoices):
        RFID = "rfid", "RFID card"
        MANUAL = "manual", "Marked by admin"
        AUTO = "auto", "Automatic (no scan)"

    student = models.ForeignKey("students.Student", on_delete=models.CASCADE, related_name="attendance_records")
    date = models.DateField(db_index=True)
    status = models.CharField(max_length=10, choices=Status.choices)
    check_in = models.DateTimeField(null=True, blank=True)
    check_out = models.DateTimeField(null=True, blank=True)
    source = models.CharField(max_length=10, choices=Source.choices, default=Source.MANUAL)
    outside_shift = models.BooleanField(default=False, help_text="Scanned outside the student's batch timings.")
    remarks = models.CharField(max_length=255, blank=True)
    marked_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["student", "date"], name="one_attendance_per_student_per_day")]
        ordering = ["-date", "student__student_id"]
        indexes = [models.Index(fields=["date", "status"])]

    def __str__(self):
        return f"{self.student_id} {self.date} {self.status}"


class StaffAttendance(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="staff_attendance")
    date = models.DateField(db_index=True)
    status = models.CharField(max_length=10, choices=Status.choices)
    remarks = models.CharField(max_length=255, blank=True)
    marked_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["user", "date"], name="one_attendance_per_staff_per_day")]
        ordering = ["-date", "user__username"]
        indexes = [models.Index(fields=["date", "status"])]

    def __str__(self):
        return f"{self.user_id} {self.date} {self.status}"
