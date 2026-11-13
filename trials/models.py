from django.db import models
from django.utils import timezone


class TrialVisitor(models.Model):
    """Someone trying the library for a day. Not a student: no ID, seat, fee or login."""

    class Status(models.TextChoices):
        VISITED = "visited", "Visited"
        JOINED = "joined", "Joined"
        NOT_JOINING = "not_joining", "Not joining"

    name = models.CharField(max_length=150)
    phone = models.CharField(max_length=20)
    trial_date = models.DateField(default=timezone.localdate)
    program = models.ForeignKey(
        "academics.Program", on_delete=models.SET_NULL, null=True, blank=True, related_name="+",
        verbose_name="Preferred batch",
    )
    notes = models.CharField(max_length=255, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.VISITED, db_index=True)
    student = models.ForeignKey(
        "students.Student", on_delete=models.SET_NULL, null=True, blank=True, related_name="+",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-trial_date", "-id"]

    def __str__(self):
        return f"{self.name} ({self.phone})"

    def mark_joined(self, student):
        self.status = self.Status.JOINED
        self.student = student
        self.save(update_fields=["status", "student"])
