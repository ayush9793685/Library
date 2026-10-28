import re
from datetime import datetime, time, timedelta
from decimal import Decimal

from django.conf import settings
from django.core.validators import FileExtensionValidator, RegexValidator
from django.db import models
from django.utils import timezone


def profile_photo_upload_to(instance, filename):
    return f"students/{instance.student_id}/profile/{filename}"


def aadhaar_copy_upload_to(instance, filename):
    return f"aadhaar/{instance.student_id}/{filename}"


def _private_storage():
    from django.core.files.storage import storages

    return storages["private"]


class Student(models.Model):
    class Gender(models.TextChoices):
        MALE = "male", "Male"
        FEMALE = "female", "Female"
        OTHER = "other", "Other"

    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        # Inactive = plan expired without payment; it ends automatically on the next payment.
        INACTIVE = "inactive", "Inactive"
        # Deactivated = permanently closed by an admin (seat freed, RFID card disabled for good).
        DEACTIVATED = "deactivated", "Deactivated"

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="student_profile")
    student_id = models.CharField(max_length=30, unique=True, db_index=True)
    first_name = models.CharField(max_length=100)
    middle_name = models.CharField(max_length=100, blank=True)
    last_name = models.CharField(max_length=100)
    date_of_birth = models.DateField(null=True, blank=True)
    gender = models.CharField(max_length=10, choices=Gender.choices, blank=True)
    nationality = models.CharField(max_length=100, blank=True)
    blood_group = models.CharField(max_length=5, blank=True)
    profile_photo = models.ImageField(
        upload_to=profile_photo_upload_to,
        blank=True,
        validators=[FileExtensionValidator(allowed_extensions=["jpg", "jpeg", "png", "webp"])],
    )

    registration_number = models.CharField(max_length=50, unique=True, db_index=True)
    department = models.ForeignKey("academics.Department", on_delete=models.PROTECT, null=True, blank=True, related_name="students")
    program = models.ForeignKey("academics.Program", on_delete=models.PROTECT, null=True, blank=True, related_name="students")
    academic_year = models.CharField(max_length=20, db_index=True)
    semester = models.CharField(max_length=20)
    enrollment_date = models.DateField(db_index=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE, db_index=True)
    subscription_end = models.DateTimeField(null=True, blank=True, db_index=True)

    # --- Fees: batch fee unless an admin sets a custom monthly fee for this student.
    custom_monthly_fee = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

    # --- Seat: fixed daily seat. seat_shift is copied from the batch so the database can
    # guarantee that two students of the same shift never hold the same seat.
    seat_number = models.PositiveSmallIntegerField(null=True, blank=True, db_index=True)
    seat_shift = models.CharField(max_length=20, blank=True, default="full_day")

    # --- RFID library card. Kept after deactivation so a disabled card can never be reissued.
    rfid_uid = models.CharField(max_length=40, unique=True, null=True, blank=True)

    # --- Aadhaar: encrypted number + keyed hash (duplicates) + last 4 digits (display) + copy.
    aadhaar_encrypted = models.TextField(blank=True)
    aadhaar_hash = models.CharField(max_length=64, unique=True, null=True, blank=True)
    aadhaar_last4 = models.CharField(max_length=4, blank=True)
    aadhaar_copy = models.FileField(
        upload_to=aadhaar_copy_upload_to,
        storage=_private_storage,
        blank=True,
        validators=[FileExtensionValidator(allowed_extensions=["pdf", "jpg", "jpeg", "png"])],
    )

    # --- Deactivation record
    deactivated_at = models.DateTimeField(null=True, blank=True)
    deactivation_reason = models.CharField(max_length=255, blank=True)
    deactivated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    released_seat = models.PositiveSmallIntegerField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            # Same seat + same shift can never be held twice (half/full-day overlap is
            # enforced in students.seats under a row lock).
            models.UniqueConstraint(
                fields=["seat_number", "seat_shift"],
                condition=models.Q(seat_number__isnull=False),
                name="unique_seat_per_shift",
            ),
        ]
        indexes = [
            models.Index(fields=["last_name", "first_name"]),
            models.Index(fields=["department", "academic_year"], name="students_st_departm_906e53_idx"),
        ]

    def __str__(self):
        return f"{self.student_id} - {self.first_name} {self.last_name}"

    ID_WIDTH = 4
    ID_MAX = 1000

    class IdsExhausted(Exception):
        """All numbers from 0001 to 1000 are in use."""

    @classmethod
    def _next_value(cls, field_name):
        """Next number as a 4-digit code (0001 ... 1000). After 1000, the lowest unused number is reused."""
        used = set()
        for value in cls.objects.values_list(field_name, flat=True):
            if value and value.isdigit():
                used.add(int(value))
        highest = max(used, default=0)
        if highest < cls.ID_MAX:
            number = highest + 1
        else:
            free = [n for n in range(1, cls.ID_MAX + 1) if n not in used]
            if not free:
                raise cls.IdsExhausted(f"All {cls.ID_MAX} numbers are in use.")
            number = free[0]
        return str(number).zfill(cls.ID_WIDTH)

    @classmethod
    def next_student_id(cls):
        return cls._next_value("student_id")

    @classmethod
    def next_registration_number(cls):
        return cls._next_value("registration_number")

    def save(self, *args, **kwargs):
        if not self.pk:
            if not self.student_id:
                self.student_id = self.next_student_id()
            if not self.registration_number:
                self.registration_number = self.next_registration_number()
            if not self.enrollment_date:
                self.enrollment_date = timezone.localdate()
            if not self.academic_year:
                self.academic_year = str(timezone.localdate().year)
            if self.status == self.Status.ACTIVE and not self.subscription_end:
                self.subscription_end = self._new_end()
        if self.program_id and self.seat_number:
            self.seat_shift = self.program.shift
        super().save(*args, **kwargs)

    # ---------------------------------------------------------------- fees
    @property
    def batch_fee(self):
        return self.program.monthly_fee if self.program_id else Decimal("0")

    @property
    def monthly_fee(self):
        """What this student pays each month: custom fee if set, else the batch fee."""
        if self.custom_monthly_fee is not None:
            return self.custom_monthly_fee
        return self.batch_fee

    @property
    def has_custom_fee(self):
        return self.custom_monthly_fee is not None

    @property
    def payment_status(self):
        """Deactivated / Paid / Unpaid / Overdue, derived from payments and plan dates."""
        if self.status == self.Status.DEACTIVATED:
            return "Deactivated"
        now = timezone.now()
        if not self.subscription_end or self.subscription_end < now:
            return "Overdue"
        has_payment = self.payments.filter(is_cancelled=False, period_end__gte=now).exists()
        return "Paid" if has_payment else "Unpaid"

    # ------------------------------------------------------------- aadhaar
    @property
    def aadhaar_masked(self):
        from .security import mask_aadhaar

        return mask_aadhaar(self.aadhaar_last4)

    def set_aadhaar(self, number):
        from .security import encrypt_aadhaar, hash_aadhaar

        self.aadhaar_encrypted = encrypt_aadhaar(number)
        self.aadhaar_hash = hash_aadhaar(number)
        self.aadhaar_last4 = number[-4:]

    # --------------------------------------------------------------- plan
    @staticmethod
    def _plan_days():
        return int(getattr(settings, "PLAN_DAYS", 30))

    @staticmethod
    def _test_seconds():
        return getattr(settings, "SUBSCRIPTION_TEST_SECONDS", None)

    @classmethod
    def _new_end(cls, base_date=None):
        """End of a plan: PLAN_DAYS (30) days from the start day, at the end of that day."""
        seconds = cls._test_seconds()
        if seconds:
            return timezone.now() + timedelta(seconds=seconds)
        end_date = (base_date or timezone.localdate()) + timedelta(days=cls._plan_days())
        return timezone.make_aware(datetime.combine(end_date, time.max))

    def renew_subscription(self, paid_on=None):
        """Called when a plan-extending payment is recorded.

        Renewal starts from the old end date when paid on time, otherwise from the
        payment day. Returns (period_start, period_end) or None if nothing changed.
        Deactivated students are never renewed.
        """
        if self.status == self.Status.DEACTIVATED:
            return None
        today = paid_on or timezone.localdate()
        old_end = timezone.localtime(self.subscription_end).date() if self.subscription_end else None
        if self._test_seconds():
            self.restart_subscription()
            return today, timezone.localtime(self.subscription_end).date()
        base = old_end if old_end and old_end >= today else today
        self.subscription_end = self._new_end(base)
        if self.status == self.Status.INACTIVE:
            self.status = self.Status.ACTIVE
        self.save(update_fields=["subscription_end", "status", "updated_at"])
        return base, timezone.localtime(self.subscription_end).date()

    def restart_subscription(self):
        """Start a fresh plan period from now (used by the test-seconds mode only)."""
        self.subscription_end = self._new_end()
        if self.status != self.Status.DEACTIVATED:
            self.status = self.Status.ACTIVE
        self.save(update_fields=["subscription_end", "status", "updated_at"])

    @classmethod
    def expire_overdue(cls):
        # Active students without an end date yet get a fresh period starting now.
        cls.objects.filter(
            status=cls.Status.ACTIVE, subscription_end__isnull=True
        ).update(subscription_end=cls._new_end())
        # Expired plans become Inactive (NOT Deactivated) until the next payment.
        return cls.objects.filter(
            status=cls.Status.ACTIVE,
            subscription_end__lt=timezone.now(),
        ).update(status=cls.Status.INACTIVE)

    @property
    def can_scan(self):
        return self.status == self.Status.ACTIVE


class ContactInformation(models.Model):
    student = models.OneToOneField(Student, on_delete=models.CASCADE, related_name="contact")
    primary_email = models.EmailField(unique=True)
    secondary_email = models.EmailField(blank=True)
    mobile_number = models.CharField(max_length=20, validators=[RegexValidator(r"^[0-9+\-() ]+$")])
    alternate_mobile_number = models.CharField(max_length=20, blank=True, validators=[RegexValidator(r"^[0-9+\-() ]*$")])


class Address(models.Model):
    class AddressType(models.TextChoices):
        PRESENT = "present", "Present"
        PERMANENT = "permanent", "Permanent"

    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name="addresses")
    address_type = models.CharField(max_length=20, choices=AddressType.choices)
    address_line_1 = models.CharField(max_length=255)
    address_line_2 = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=120)
    state = models.CharField(max_length=120)
    postal_code = models.CharField(max_length=20)
    country = models.CharField(max_length=100)

    class Meta:
        unique_together = ("student", "address_type")


class EmergencyContact(models.Model):
    student = models.OneToOneField(Student, on_delete=models.CASCADE, related_name="emergency_contact")
    contact_name = models.CharField(max_length=150)
    relationship = models.CharField(max_length=80)
    mobile_number = models.CharField(max_length=20)
    email_address = models.EmailField(blank=True)
