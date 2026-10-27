from django.db import models


class RegistrationWindow(models.Model):
    name = models.CharField(max_length=120)
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField()
    is_active = models.BooleanField(default=True)


class CourseOffering(models.Model):
    course_code_text = models.CharField(max_length=20, db_index=True, blank=True)
    course = models.ForeignKey("academics.Course", on_delete=models.PROTECT, null=True, blank=True, related_name="offerings")
    semester = models.CharField(max_length=20)
    capacity = models.PositiveIntegerField(default=40)
    registration_window = models.ForeignKey(RegistrationWindow, on_delete=models.PROTECT, related_name="offerings")


class CourseRegistration(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        APPROVED = "approved", "Approved"
        DROPPED = "dropped", "Dropped"

    student_id_text = models.CharField(max_length=30, db_index=True, blank=True)
    student = models.ForeignKey("students.Student", on_delete=models.CASCADE, null=True, blank=True, related_name="course_registrations")
    offering = models.ForeignKey(CourseOffering, on_delete=models.CASCADE, related_name="registrations")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    registered_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("student", "offering")

# Create your models here.
