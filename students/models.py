import calendar
import re
from datetime import date, datetime, time, timedelta

from django.conf import settings
from django.core.validators import FileExtensionValidator, RegexValidator
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone


def profile_photo_upload_to(instance, filename):
    return f"students/{instance.student_id}/profile/{filename}"


class Student(models.Model):
    class Gender(models.TextChoices):
        MALE = "male", "Male"
        FEMALE = "female", "Female"
        OTHER = "other", "Other"

    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        INACTIVE = "inactive", "Inactive"

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

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["last_name", "first_name"]),
            models.Index(fields=["department", "academic_year"], name="students_st_departm_906e53_idx"),
        ]

    def __str__(self):
        return f"{self.student_id} - {self.first_name} {self.last_name}"

    @classmethod
    def _next_value(cls, field_name):
        best = None
        for value in cls.objects.values_list(field_name, flat=True):
            match = re.match(r"^(.*?)(\d+)$", value or "")
            if match:
                number = int(match.group(2))
                if best is None or number > best[0]:
                    best = (number, match.group(1), len(match.group(2)))
        if best is None:
            return "1"
        number, prefix, width = best
        return f"{prefix}{str(number + 1).zfill(width)}"

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
            if self.status == self.Status.ACTIVE and not self.subscription_end:
                self.subscription_end = self._new_end()
        super().save(*args, **kwargs)

    @staticmethod
    def _add_one_month(d):
        year = d.year + d.month // 12
        month = d.month % 12 + 1
        day = min(d.day, calendar.monthrange(year, month)[1])
        return date(year, month, day)

    @staticmethod
    def _test_seconds():
        return getattr(settings, "SUBSCRIPTION_TEST_SECONDS", None)

    @classmethod
    def _new_end(cls, base_date=None):
        """End of a one-month subscription (or a few seconds in test mode)."""
        seconds = cls._test_seconds()
        if seconds:
            return timezone.now() + timedelta(seconds=seconds)
        end_date = cls._add_one_month(base_date or timezone.localdate())
        return timezone.make_aware(datetime.combine(end_date, time.max))

    def renew_subscription(self):
        """Called on payment: extends by one month, never beyond one month ahead."""
        if self._test_seconds():
            return self.restart_subscription()
        today = timezone.localdate()
        end_date = timezone.localtime(self.subscription_end).date() if self.subscription_end else None
        if end_date and end_date > self._add_one_month(today):
            return  # already paid for the one month allowed
        base = end_date if end_date and end_date >= today else today
        self.subscription_end = self._new_end(base)
        if self.status == self.Status.INACTIVE:
            self.status = self.Status.ACTIVE
        self.save(update_fields=["subscription_end", "status", "updated_at"])

    def restart_subscription(self):
        """Start a fresh subscription period from now and activate."""
        self.subscription_end = self._new_end()
        self.status = self.Status.ACTIVE
        self.save(update_fields=["subscription_end", "status", "updated_at"])

    @classmethod
    def expire_overdue(cls):
        # Active students without an end date yet get a fresh period starting now.
        cls.objects.filter(
            status=cls.Status.ACTIVE, subscription_end__isnull=True
        ).update(subscription_end=cls._new_end())
        return cls.objects.filter(
            status=cls.Status.ACTIVE,
            subscription_end__lt=timezone.now(),
        ).update(status=cls.Status.INACTIVE)


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

@receiver(post_save, sender="fees.Payment")
def renew_subscription_on_payment(sender, instance, created, **kwargs):
    # Only the monthly library fee keeps the subscription going; the yearly
    # registration fee does not extend it.
    if created and instance.student and instance.fee_structure.fee_type == "library":
        instance.student.renew_subscription()