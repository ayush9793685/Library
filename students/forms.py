import re
from decimal import Decimal

from django import forms
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.db import IntegrityError, transaction

from academics.models import Program
from audits.utils import create_audit_log

from . import seats
from .models import Address, ContactInformation, EmergencyContact, Student
from .security import hash_aadhaar, validate_aadhaar


class SeatUnavailable(Exception):
    pass


_MAGIC = {
    "pdf": (b"%PDF",),
    "jpg": (b"\xff\xd8\xff",),
    "jpeg": (b"\xff\xd8\xff",),
    "png": (b"\x89PNG",),
}


class DateInput(forms.DateInput):
    input_type = "date"


# Fields only an administrator may change.
ADMIN_ONLY_FIELDS = [
    "student_id", "registration_number", "program", "monthly_fee", "seat_number", "rfid_uid",
    "aadhaar_number", "aadhaar_copy", "confirm_batch_change",
]


class StudentForm(forms.ModelForm):
    mobile_number = forms.CharField(
        label="Phone Number",
        max_length=20,
        validators=[RegexValidator(r"^[0-9+\-() ]+$", "Enter a valid phone number.")],
    )
    primary_email = forms.EmailField(label="Email")
    alternate_mobile_number = forms.CharField(
        label="Alternate Phone Number (optional)",
        max_length=20,
        required=False,
        validators=[RegexValidator(r"^[0-9+\-() ]*$", "Enter a valid phone number.")],
    )

    program = forms.ModelChoiceField(label="Batch", queryset=Program.objects.none(), empty_label="Select batch")
    monthly_fee = forms.DecimalField(
        label="Monthly Fee (Rs.)", min_value=Decimal("0"), max_digits=10, decimal_places=2,
        help_text="Fills in automatically from the batch. Admins can change it for this student only.",
    )
    seat_number = forms.IntegerField(
        label="Seat Number", required=False, min_value=1,
        help_text="Leave blank to allot a seat automatically. Admins can pick a specific free seat.",
    )
    rfid_uid = forms.CharField(
        label="RFID Card Number", required=False, max_length=40,
        help_text="Scan the library card into this box (optional now, needed for attendance).",
    )
    aadhaar_number = forms.CharField(
        label="Aadhaar Number", max_length=14, required=False,
        help_text="12 digits. Stored encrypted; only the last 4 digits are ever shown.",
    )
    aadhaar_copy = forms.FileField(
        label="Aadhaar Copy (PDF / JPG / PNG)", required=False,
        help_text="Photocopy or scan of the Aadhaar card, max 5 MB. Visible only to admins with the password.",
    )

    # create-only
    collect_fee = forms.BooleanField(
        label="Collect the first month's fee now", required=False, initial=True,
        help_text="Records a receipt for the first 30 days.",
    )
    payment_mode = forms.ChoiceField(label="Payment Mode", required=False, choices=[("cash", "Cash"), ("upi", "UPI")])
    payment_reference = forms.CharField(label="UPI Transaction ID (UTR)", required=False, max_length=60)

    # edit-only
    confirm_batch_change = forms.BooleanField(label="I confirm the batch change", required=False)

    field_order = [
        "student_id", "registration_number", "first_name", "middle_name", "last_name",
        "date_of_birth", "gender", "mobile_number", "primary_email", "alternate_mobile_number",
        "program", "monthly_fee", "seat_number", "rfid_uid",
        "aadhaar_number", "aadhaar_copy", "profile_photo",
        "collect_fee", "payment_mode", "payment_reference", "confirm_batch_change",
    ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.is_new = not (self.instance and self.instance.pk)
        self.fee_map = {}

        for required_name in ["first_name", "last_name"]:
            self.fields[required_name].required = True

        batches = Program.objects.filter(is_active=True).order_by("monthly_fee", "name")
        self.fields["program"].queryset = batches
        self.fee_map = {str(b.pk): str(b.monthly_fee) for b in batches}
        self.batch_info = [
            {"id": b.pk, "name": b.name, "fee": b.monthly_fee, "timing": b.timing_display, "shift": b.shift}
            for b in batches
        ]
        self.fields["program"].label_from_instance = (
            lambda b: f"{b.name} ({b.timing_display}) - Rs. {b.monthly_fee:g}/month" if b.timing_display
            else f"{b.name} - Rs. {b.monthly_fee:g}/month"
        )
        self.fields["program"].widget.attrs["data-fees"] = ",".join(f"{k}:{v}" for k, v in self.fee_map.items())

        if self.is_new:
            self.fields["aadhaar_number"].required = True
            self.fields["aadhaar_copy"].required = True
            self.fields.pop("confirm_batch_change")
        else:
            for name in ("collect_fee", "payment_mode", "payment_reference"):
                self.fields.pop(name)
            self.initial["monthly_fee"] = self.instance.monthly_fee
            self.initial["seat_number"] = self.instance.seat_number
            self.fields["aadhaar_number"].help_text = (
                f"Stored: {self.instance.aadhaar_masked}. Leave blank to keep it, or type a new number to replace it."
            )
            self.fields["aadhaar_copy"].help_text = "Leave empty to keep the current copy."
            self.fields["confirm_batch_change"].help_text = (
                "Needed only if you change the batch. The new fee applies from the next renewal, "
                "past payments stay as recorded, and the seat is re-checked for the new timings."
            )
            if self.instance.status == Student.Status.DEACTIVATED:
                for name in ("program", "monthly_fee", "seat_number"):
                    self.fields[name].disabled = True
                self.fields["seat_number"].help_text = "Deactivated students hold no seat."

        if self.instance and self.instance.pk:
            contact = getattr(self.instance, "contact", None)
            if contact:
                self.initial["mobile_number"] = contact.mobile_number
                self.initial["primary_email"] = contact.primary_email
                self.initial["alternate_mobile_number"] = contact.alternate_mobile_number

        for name, field in self.fields.items():
            widget = field.widget
            if isinstance(widget, forms.CheckboxInput):
                continue
            if isinstance(widget, forms.FileInput):
                widget.attrs.update({
                    "class": "block w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm file:mr-4 file:rounded-md file:border-0 file:bg-slate-900 file:px-3 file:py-2 file:text-sm file:font-medium file:text-white hover:file:bg-slate-700",
                })
            else:
                widget.attrs.update({
                    "class": "w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm outline-none transition focus:border-slate-600 focus:ring-2 focus:ring-slate-200",
                })
            if name in ["date_of_birth"]:
                field.widget.attrs.update({"max": "2100-12-31"})
            field.label = field.label.replace("_", " ")

        self.fields["aadhaar_number"].widget.attrs.update({"autocomplete": "off", "inputmode": "numeric"})
        self.fields["rfid_uid"].widget.attrs.update({"autocomplete": "off"})

        for auto_name, next_value in [
            ("student_id", Student.next_student_id),
            ("registration_number", Student.next_registration_number),
        ]:
            auto_field = self.fields[auto_name]
            auto_field.required = False
            auto_field.widget.attrs["readonly"] = True
            auto_field.widget.attrs["class"] += " bg-slate-100 text-slate-500"
            if self.is_new:
                try:
                    self.initial[auto_name] = next_value()
                except Student.IdsExhausted:
                    self.initial[auto_name] = ""

    class Meta:
        model = Student
        fields = [
            "student_id", "registration_number", "first_name", "middle_name", "last_name",
            "date_of_birth", "gender", "program", "rfid_uid", "profile_photo",
        ]
        widgets = {
            "date_of_birth": DateInput(attrs={"placeholder": "YYYY-MM-DD"}),
        }

    # ------------------------------------------------------------ field cleaning
    def clean_primary_email(self):
        email = self.cleaned_data["primary_email"].strip()
        clash = ContactInformation.objects.filter(primary_email__iexact=email)
        if self.instance.pk:
            clash = clash.exclude(student=self.instance)
        if clash.exists():
            raise forms.ValidationError("This email is already used by another student.")
        return email

    def clean_student_id(self):
        if self.instance.pk:
            return self.instance.student_id
        try:
            return Student.next_student_id()
        except Student.IdsExhausted as exc:
            raise forms.ValidationError(str(exc))

    def clean_registration_number(self):
        if self.instance.pk:
            return self.instance.registration_number
        try:
            return Student.next_registration_number()
        except Student.IdsExhausted as exc:
            raise forms.ValidationError(str(exc))

    def clean_rfid_uid(self):
        value = (self.cleaned_data.get("rfid_uid") or "").strip()
        if not value:
            return None
        clash = Student.objects.filter(rfid_uid__iexact=value)
        if self.instance.pk:
            clash = clash.exclude(pk=self.instance.pk)
        other = clash.first()
        if other:
            raise forms.ValidationError(
                f"This card is already linked to {other.student_id}."
                + (" That card was permanently disabled and cannot be reused." if other.status == Student.Status.DEACTIVATED else "")
            )
        return value

    def clean_aadhaar_number(self):
        raw = (self.cleaned_data.get("aadhaar_number") or "").strip()
        if not raw:
            if self.is_new:
                raise forms.ValidationError("Aadhaar number is compulsory.")
            return ""
        number = validate_aadhaar(raw)
        clash = Student.objects.filter(aadhaar_hash=hash_aadhaar(number))
        if self.instance.pk:
            clash = clash.exclude(pk=self.instance.pk)
        other = clash.first()
        if other:
            raise forms.ValidationError(f"This Aadhaar number is already registered for student {other.student_id}.")
        return number

    def clean_aadhaar_copy(self):
        upload = self.cleaned_data.get("aadhaar_copy")
        if not upload:
            if self.is_new:
                raise forms.ValidationError("Aadhaar copy is compulsory.")
            return upload
        if not hasattr(upload, "size"):  # existing file, unchanged
            return upload
        limit = int(getattr(settings, "AADHAAR_COPY_MAX_MB", 5))
        if upload.size > limit * 1024 * 1024:
            raise forms.ValidationError(f"The file is too large (max {limit} MB).")
        ext = upload.name.rsplit(".", 1)[-1].lower() if "." in upload.name else ""
        if ext not in _MAGIC:
            raise forms.ValidationError("Upload a PDF, JPG or PNG file.")
        header = upload.read(8)
        upload.seek(0)
        if not any(header.startswith(sig) for sig in _MAGIC[ext]):
            raise forms.ValidationError("This file does not look like a real PDF/JPG/PNG.")
        return upload

    def clean_seat_number(self):
        seat = self.cleaned_data.get("seat_number")
        if seat and seat > seats.total_seats():
            raise forms.ValidationError(f"Seats are numbered 1 to {seats.total_seats()}.")
        return seat

    # --------------------------------------------------------------- whole form
    def _program_changed(self):
        return bool(self.instance.pk and "program" in self.changed_data
                    and self.instance.program_id != self.cleaned_data["program"].pk)

    def clean(self):
        cleaned = super().clean()
        program = cleaned.get("program")
        if not program:
            return cleaned
        self.instance.department = program.department

        if self.is_new:
            fee = cleaned.get("monthly_fee")
            if cleaned.get("collect_fee") and fee is not None and fee <= 0:
                self.add_error("monthly_fee", "Set a fee above zero to collect payment.")
            if cleaned.get("collect_fee") and not cleaned.get("payment_mode"):
                self.add_error("payment_mode", "Choose Cash or UPI.")
        elif self._program_changed() and not cleaned.get("confirm_batch_change"):
            new_fee = program.monthly_fee
            self.add_error(
                "confirm_batch_change",
                f"You are moving this student from {self.instance.program} to {program.name}. "
                f"New fee: Rs. {new_fee:g}/month (from the next renewal; past payments are unchanged). "
                "Tick this box and save again to confirm.",
            )

        # Early seat feedback (the final, locked check happens in save_all()).
        shift = program.shift
        requested = cleaned.get("seat_number")
        keep_current = (
            not self.is_new and self.instance.seat_number and self.instance.program_id
            and self.instance.program.shift == shift
        )
        if self.instance.status != Student.Status.DEACTIVATED:
            exclude = self.instance.pk
            if requested:
                if not seats.seat_is_free(requested, shift, exclude):
                    self.add_error("seat_number", f"Seat {requested} is not free for the {program.name} timings.")
            elif not keep_current and seats.pick_seat(shift, exclude) is None:
                self.add_error("program", f"No seat is available for the {program.name} batch right now.")
        return cleaned

    # --------------------------------------------------------------------- save
    def save_contact(self, student):
        ContactInformation.objects.update_or_create(
            student=student,
            defaults={
                "primary_email": self.cleaned_data["primary_email"],
                "mobile_number": self.cleaned_data["mobile_number"],
                "alternate_mobile_number": self.cleaned_data.get("alternate_mobile_number", ""),
            },
        )

    def save_all(self, user=None):
        """Save student, seat, fee, Aadhaar, contact and (on create) the first payment.

        Returns (student, payment_or_None). Raises SeatUnavailable if the seat was taken
        between validation and saving.
        """
        from fees.services import record_payment

        data = self.cleaned_data
        program = data["program"]
        shift = program.shift
        payment = None
        try:
            with transaction.atomic():
                seats.lock_seat_rows()
                student = super().save(commit=False)
                old_seat = student.seat_number if student.pk else None
                student.department = program.department

                # --- fee: a custom fee is stored only when it differs from the batch fee
                fee = data["monthly_fee"]
                student.custom_monthly_fee = None if fee == program.monthly_fee else fee

                # --- seat
                if student.status != Student.Status.DEACTIVATED:
                    requested = data.get("seat_number")
                    if requested:
                        seat = requested if seats.seat_is_free(requested, shift, student.pk) else None
                    elif old_seat and (not self.is_new) and seats.seat_is_free(old_seat, shift, student.pk):
                        seat = old_seat  # same seat every day, as long as it still fits
                    else:
                        seat = seats.pick_seat(shift, student.pk)
                    if seat is None:
                        raise SeatUnavailable("No seat is free for this batch.")
                    student.seat_number = seat
                    student.seat_shift = shift

                # --- Aadhaar
                if data.get("aadhaar_number"):
                    student.set_aadhaar(data["aadhaar_number"])
                upload = data.get("aadhaar_copy")
                if upload and hasattr(upload, "size"):
                    student.aadhaar_copy = upload

                student.save()
                self.save_contact(student)
                self._save_m2m()

                if self.is_new and data.get("collect_fee"):
                    payment = record_payment(
                        student, mode=data["payment_mode"], reference=data.get("payment_reference", ""),
                        user=user, registration=True,
                    )
        except IntegrityError as exc:
            raise SeatUnavailable("That seat was just taken by another student. Please try again.") from exc

        action = "student_create" if self.is_new else "profile_update"
        if self.is_new:
            create_audit_log(user=user, action=action, object_modified=student.student_id,
                             new_value=f"{program.name}, seat {student.seat_number}, fee {student.monthly_fee}")
        elif "program" in self.changed_data or (old_seat != student.seat_number):
            create_audit_log(
                user=user, action="batch_or_seat_change", object_modified=student.student_id,
                old_value=f"seat {old_seat}", new_value=f"{program.name}, seat {student.seat_number}, fee {student.monthly_fee}",
            )
        return student, payment


class ContactInformationForm(forms.ModelForm):
    class Meta:
        model = ContactInformation
        exclude = ("student",)


class AddressForm(forms.ModelForm):
    class Meta:
        model = Address
        exclude = ("student", "address_type")


class EmergencyContactForm(forms.ModelForm):
    class Meta:
        model = EmergencyContact
        exclude = ("student",)