from django.db import models


class Announcement(models.Model):
    title = models.CharField(max_length=180)
    description = models.TextField()
    publish_date = models.DateField()
    expiry_date = models.DateField(null=True, blank=True)
    department_name = models.CharField(max_length=100, blank=True)
    department = models.ForeignKey("academics.Department", on_delete=models.SET_NULL, null=True, blank=True, related_name="announcements")
    semester = models.CharField(max_length=20, blank=True)
    is_active = models.BooleanField(default=True)


class Notification(models.Model):
    student_id_text = models.CharField(max_length=30, db_index=True, blank=True)
    student = models.ForeignKey("students.Student", on_delete=models.CASCADE, null=True, blank=True, related_name="notifications")
    title = models.CharField(max_length=180)
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

# Create your models here.
