import re

from django import forms
from django.core.validators import RegexValidator
from django.utils import timezone

from academics.forms import QuickProgramForm
from academics.models import Department, Program

from .models import Address, ContactInformation, EmergencyContact, Student


OTHER_PROGRAM = "__other__"


class ProgramChoiceField(forms.ModelChoiceField):
    """Program select that also accepts the 'Other (add new program)' option."""

    def to_python(self, value):
        if value == OTHER_PROGRAM:
            return None
        return super().to_python(value)


class DateInput(forms.DateInput):
    input_type = "date"


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

    program = ProgramChoiceField(label="Program", queryset=Program.objects.none(), required=False)
    new_program_name = forms.CharField(label="New Program Name", max_length=120, required=False)

    field_order = [
        "student_id",
        "first_name",
        "middle_name",
        "last_name",
        "date_of_birth",
        "gender",
        "mobile_number",
        "primary_email",
        "alternate_mobile_number",
        "program",
        "new_program_name",
        "profile_photo",
    ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        for required_name in ["first_name", "last_name"]:
            self.fields[required_name].required = True

        self.fields["program"].queryset = Program.objects.filter(is_active=True).select_related("department").order_by("name")
        self.fields["program"].choices = (
            [("", "Select Program")]
            + [(p.pk, str(p)) for p in self.fields["program"].queryset]
            + [(OTHER_PROGRAM, "Other (add new program)")]
        )
        current_year = timezone.localdate().year
        academic_year_choices = [("", "Select Academic Year")] + [
            (str(year), str(year)) for year in range(current_year, 1999, -1)
        ]
        self.fields["academic_year"].widget = forms.Select(choices=academic_year_choices)

        if self.instance and self.instance.pk:
            for field_name in ["academic_year"]:
                current_value = getattr(self.instance, field_name, "")
                if current_value and current_value not in dict(self.fields[field_name].widget.choices):
                    self.fields[field_name].widget.choices = list(self.fields[field_name].widget.choices) + [
                        (current_value, current_value)
                    ]

        if self.instance and self.instance.pk:
            contact = getattr(self.instance, "contact", None)
            if contact:
                self.initial["mobile_number"] = contact.mobile_number
                self.initial["primary_email"] = contact.primary_email
                self.initial["alternate_mobile_number"] = contact.alternate_mobile_number

        for name, field in self.fields.items():
            if isinstance(field.widget, forms.FileInput):
                field.widget.attrs.update(
                    {
                        "class": "block w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm file:mr-4 file:rounded-md file:border-0 file:bg-slate-900 file:px-3 file:py-2 file:text-sm file:font-medium file:text-white hover:file:bg-slate-700",
                    }
                )
            else:
                field.widget.attrs.update(
                    {
                        "class": "w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm outline-none transition focus:border-slate-600 focus:ring-2 focus:ring-slate-200",
                    }
                )

            if name in ["date_of_birth", "enrollment_date"]:
                field.widget.attrs.update({"max": "2100-12-31"})

            field.label = field.label.replace("_", " ").title()

        for auto_name, next_value in [
            ("student_id", Student.next_student_id),
            ("registration_number", Student.next_registration_number),
        ]:
            auto_field = self.fields[auto_name]
            auto_field.required = False
            auto_field.widget.attrs["readonly"] = True
            auto_field.widget.attrs["class"] += " bg-slate-100 text-slate-500"
            if not self.instance.pk:
                self.initial[auto_name] = next_value()

    class Meta:
        model = Student
        exclude = ("user", "created_at", "updated_at", "nationality", "blood_group", "department", "subscription_end", "semester")
        widgets = {
            "date_of_birth": DateInput(attrs={"placeholder": "YYYY-MM-DD"}),
            "enrollment_date": DateInput(attrs={"placeholder": "YYYY-MM-DD"}),
        }

    def clean_academic_year(self):
        value = self.cleaned_data["academic_year"]
        match = re.match(r"^\d{4}", value or "")
        if match and int(match.group()) > timezone.localdate().year:
            raise forms.ValidationError("Academic year cannot be later than the current year.")
        return value

    def clean_primary_email(self):
        email = self.cleaned_data["primary_email"].strip()
        clash = ContactInformation.objects.filter(primary_email__iexact=email)
        if self.instance.pk:
            clash = clash.exclude(student=self.instance)
        if clash.exists():
            raise forms.ValidationError("This email is already used by another student.")
        return email

    def save_contact(self, student):
        ContactInformation.objects.update_or_create(
            student=student,
            defaults={
                "primary_email": self.cleaned_data["primary_email"],
                "mobile_number": self.cleaned_data["mobile_number"],
                "alternate_mobile_number": self.cleaned_data.get("alternate_mobile_number", ""),
            },
        )

    def clean_student_id(self):
        if self.instance.pk:
            return self.instance.student_id
        return Student.next_student_id()

    def clean_registration_number(self):
        if self.instance.pk:
            return self.instance.registration_number
        return Student.next_registration_number()

    def clean(self):
        cleaned_data = super().clean()
        self._new_program_name = None
        program = cleaned_data.get("program")
        if not program:
            if self.data.get(self.add_prefix("program")) == OTHER_PROGRAM:
                name = (cleaned_data.get("new_program_name") or "").strip()
                if not name:
                    self.add_error("new_program_name", "Enter the new program name.")
                else:
                    program = Program.objects.filter(name__iexact=name).first()
                    if program:
                        cleaned_data["program"] = program
                    else:
                        self._new_program_name = name
            elif "program" not in self.errors:
                self.add_error("program", "This field is required.")
        if program:
            self.instance.department = program.department
        return cleaned_data

    def save(self, commit=True):
        if getattr(self, "_new_program_name", None):
            program_form = QuickProgramForm({"name": self._new_program_name})
            if program_form.is_valid():
                program = program_form.save()
                self.instance.program = program
                self.instance.department = program.department
        return super().save(commit=commit)


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