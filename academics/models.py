from django.conf import settings
from django.db import models


class Department(models.Model):
    name = models.CharField(max_length=120, unique=True)
    code = models.CharField(max_length=20, unique=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name


class Program(models.Model):
    department = models.ForeignKey(Department, on_delete=models.PROTECT, related_name="programs")
    name = models.CharField(max_length=120)
    code = models.CharField(max_length=20, unique=True)
    duration_semesters = models.PositiveSmallIntegerField(default=8)
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ("department", "name")

    def __str__(self):
        return self.name


class Course(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        ARCHIVED = "archived", "Archived"

    department = models.ForeignKey(Department, on_delete=models.PROTECT, related_name="courses")
    code = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=180)
    credit_hours = models.DecimalField(max_digits=4, decimal_places=1)
    semester = models.CharField(max_length=20)
    instructor_name = models.CharField(max_length=120, blank=True)
    instructor = models.ForeignKey("Faculty", on_delete=models.SET_NULL, null=True, blank=True, related_name="courses")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE)

    class Meta:
        indexes = [models.Index(fields=["department", "semester"])]

    def __str__(self):
        return f"{self.code} - {self.name}"


class Faculty(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="faculty_profile")
    employee_id = models.CharField(max_length=30, unique=True, db_index=True)
    full_name = models.CharField(max_length=180)
    email = models.EmailField(blank=True)
    department = models.ForeignKey(Department, on_delete=models.SET_NULL, null=True, blank=True, related_name="faculty")
    title = models.CharField(max_length=80, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.employee_id} - {self.full_name}"