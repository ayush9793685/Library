from django.db import models


class Ticket(models.Model):
    class Category(models.TextChoices):
        ACADEMIC = "academic", "Academic"
        TECHNICAL = "technical", "Technical"
        FINANCIAL = "financial", "Financial"
        GENERAL = "general", "General"

    class Status(models.TextChoices):
        OPEN = "open", "Open"
        IN_PROGRESS = "in_progress", "In Progress"
        RESOLVED = "resolved", "Resolved"
        CLOSED = "closed", "Closed"

    student_id_text = models.CharField(max_length=30, db_index=True, blank=True)
    student = models.ForeignKey("students.Student", on_delete=models.CASCADE, null=True, blank=True, related_name="tickets")
    subject = models.CharField(max_length=180)
    description = models.TextField()
    category = models.CharField(max_length=20, choices=Category.choices)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.OPEN)
    created_at = models.DateTimeField(auto_now_add=True)


class TicketReply(models.Model):
    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name="replies")
    author_name_text = models.CharField(max_length=120, blank=True)
    author = models.ForeignKey("accounts.User", on_delete=models.SET_NULL, null=True, blank=True, related_name="ticket_replies")
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

# Create your models here.
