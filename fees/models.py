from decimal import Decimal

from django.conf import settings
from django.db import models


class FeeStructure(models.Model):
    """Legacy table, kept only so existing databases migrate safely.

    The library now charges one monthly fee per batch (see academics.Program.monthly_fee)
    or a custom per-student fee; the old Registration / Library fee types are no longer used.
    """

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
    class Mode(models.TextChoices):
        CASH = "cash", "Cash"
        UPI = "upi", "UPI"

    student_id_text = models.CharField(max_length=30, db_index=True, blank=True)
    student = models.ForeignKey("students.Student", on_delete=models.CASCADE, null=True, blank=True, related_name="payments")
    # Legacy link; new payments have no fee structure.
    fee_structure = models.ForeignKey(FeeStructure, on_delete=models.PROTECT, related_name="payments", null=True, blank=True)
    amount_paid = models.DecimalField(max_digits=10, decimal_places=2)
    paid_on = models.DateField()
    # For UPI: the transaction id (UTR) from the UPI app. Optional for cash.
    reference = models.CharField(max_length=60, blank=True)

    payment_mode = models.CharField(max_length=10, choices=Mode.choices, default=Mode.CASH)
    receipt_number = models.CharField(max_length=20, unique=True, null=True, blank=True)
    # The 30-day plan this payment covers.
    period_start = models.DateField(null=True, blank=True)
    period_end = models.DateField(null=True, blank=True)
    # The first month paid at registration does not extend the plan that registration already set.
    extends_plan = models.BooleanField(default=True)
    # Plan end date before this payment, so a cancelled receipt can restore it exactly.
    previous_plan_end = models.DateTimeField(null=True, blank=True)

    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True, null=True)

    # Receipts are never edited or deleted: a mistake is cancelled with a reason.
    is_cancelled = models.BooleanField(default=False)
    cancel_reason = models.CharField(max_length=255, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    cancelled_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+")

    class Meta:
        ordering = ["-paid_on", "-id"]

    def __str__(self):
        return f"{self.receipt_number or self.pk} - {self.amount_paid}"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if not self.receipt_number:
            self.receipt_number = f"RC-{self.pk:06d}"
            Payment.objects.filter(pk=self.pk).update(receipt_number=self.receipt_number)

    @property
    def student_name(self):
        if not self.student:
            return self.student_id_text
        return " ".join(p for p in [self.student.first_name, self.student.middle_name, self.student.last_name] if p)
