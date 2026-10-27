from django.db import models

from academics.models import Course


class Enrollment(models.Model):
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name="enrollments")
    student_id = models.CharField(max_length=30, db_index=True)
    enrolled_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("course", "student_id")
        verbose_name = "Enrollment"
        verbose_name_plural = "Enrollments"

    def __str__(self):
        return f"{self.student_id} -> {self.course.code}"


class AttendanceSession(models.Model):
    class TimeSlot(models.TextChoices):
        MORNING = "morning", "Morning (08:00–10:00)"
        MID_MORNING = "mid_morning", "Mid-Morning (10:00–12:00)"
        AFTERNOON = "afternoon", "Afternoon (12:00–14:00)"
        MID_AFTERNOON = "mid_afternoon", "Mid-Afternoon (14:00–16:00)"
        EVENING = "evening", "Evening (16:00–18:00)"

    session_date = models.DateField(db_index=True)
    course = models.ForeignKey(Course, on_delete=models.PROTECT, related_name="attendance_sessions")
    department = models.ForeignKey("academics.Department", on_delete=models.PROTECT, related_name="attendance_sessions", null=True, blank=True)
    program = models.ForeignKey("academics.Program", on_delete=models.PROTECT, related_name="attendance_sessions", null=True, blank=True)
    semester = models.CharField(max_length=20)
    instructor_name = models.CharField(max_length=120, blank=True)
    instructor = models.ForeignKey("academics.Faculty", on_delete=models.SET_NULL, null=True, blank=True, related_name="attendance_sessions")
    time_slot = models.CharField(max_length=30, choices=TimeSlot.choices, default=TimeSlot.MORNING)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["department", "semester"]),
            models.Index(fields=["course", "session_date"]),
        ]

    def __str__(self):
        return f"{self.course.code} – {self.session_date} ({self.get_time_slot_display()})"


class AttendanceRecord(models.Model):
    class Status(models.TextChoices):
        PRESENT = "present", "Present"
        ABSENT = "absent", "Absent"
        LATE = "late", "Late"
        EXCUSED = "excused", "Excused"

    session = models.ForeignKey(AttendanceSession, on_delete=models.CASCADE, related_name="records")
    enrollment = models.ForeignKey(Enrollment, on_delete=models.CASCADE, related_name="attendance_records", null=True, blank=True)
    student_id = models.CharField(max_length=30, db_index=True)
    status = models.CharField(max_length=20, choices=Status.choices)
    remarks = models.CharField(max_length=255, blank=True)

    class Meta:
        unique_together = ("session", "student_id")

    def __str__(self):
        return f"{self.student_id} – {self.status} ({self.session})"
