from django import forms
from django.utils import timezone

from students.models import Student

from .models import Payment
from .services import PaymentError, check_can_pay


class PaymentForm(forms.Form):
    student = forms.CharField(
        label="Student ID",
        max_length=30,
        widget=forms.TextInput(attrs={
            "placeholder": "Type student ID",
            "autocomplete": "off",
            "data-student-search": "/fees/students/search/",
        }),
    )
    payment_mode = forms.ChoiceField(label="Payment Mode", choices=Payment.Mode.choices, initial=Payment.Mode.CASH)
    reference = forms.CharField(
        label="UPI Transaction ID (UTR)", max_length=60, required=False,
        help_text="Required for UPI. Copy it from the UPI app's payment details.",
    )
    paid_on = forms.DateField(label="Payment Date", widget=forms.DateInput(attrs={"type": "date"}), initial=timezone.localdate)

    def clean_student(self):
        student_id = self.cleaned_data["student"].strip()
        student = Student.objects.select_related("program").filter(student_id__iexact=student_id).first()
        if student is None:
            raise forms.ValidationError("No student found with this ID.")
        return student

    def clean_paid_on(self):
        value = self.cleaned_data["paid_on"]
        if value > timezone.localdate():
            raise forms.ValidationError("The payment date cannot be in the future.")
        return value

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("payment_mode") == Payment.Mode.UPI and not (cleaned.get("reference") or "").strip():
            self.add_error("reference", "Enter the UPI transaction ID.")
        student = cleaned.get("student")
        if student:
            try:
                self.fee = check_can_pay(student)
            except PaymentError as exc:
                self.add_error("student", str(exc))
        return cleaned


class CancelPaymentForm(forms.Form):
    reason = forms.CharField(label="Reason for cancelling", max_length=255)
