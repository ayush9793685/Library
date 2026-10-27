from django.db import models


class Document(models.Model):
    class Category(models.TextChoices):
        CALENDAR = "calendar", "Academic Calendar"
        ENROLLMENT_CERT = "enrollment_certificate", "Enrollment Certificate"
        TRANSCRIPT = "transcript", "Transcript"
        NOTICE = "notice", "Notice"
        CIRCULAR = "circular", "Circular"
        ID_CARD = "id_card", "Student ID Card"

    title = models.CharField(max_length=180)
    category = models.CharField(max_length=30, choices=Category.choices)
    file = models.FileField(upload_to="documents/")
    is_public = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

# Create your models here.
