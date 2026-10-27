from django.db import models


class FeeStructure(models.Model):
    class FeeType(models.TextChoices):
        REGISTRATION = "registration", "Registration Fee (once a year)"
        LIBRARY = "library", "Library Fee (monthly)"

    fee_type = models.CharField(max_length=30, choices=FeeType.choices)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    academic_year = models.CharField(max_length=20)
    semester = models.CharField(max_length=20, blank=True, default="")  # no longer used

    def __str__(self):
        return f"{self.get_fee_type_display()} - {self.academic_year} ({self.amount})"


class Payment(models.Model):
    student_id_text = models.CharField(max_length=30, db_index=True, blank=True)
    student = models.ForeignKey("students.Student", on_delete=models.CASCADE, null=True, blank=True, related_name="payments")
    fee_structure = models.ForeignKey(FeeStructure, on_delete=models.PROTECT, related_name="payments")
    amount_paid = models.DecimalField(max_digits=10, decimal_places=2)
    paid_on = models.DateField()
    reference = models.CharField(max_length=60, blank=True)

# Create your models here.
