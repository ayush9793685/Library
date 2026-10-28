from django import forms
from django.utils import timezone

from academics.models import Program

from .models import Status


class DayFilterForm(forms.Form):
    date = forms.DateField(label="Date", widget=forms.DateInput(attrs={"type": "date"}), initial=timezone.localdate)
    batch = forms.ModelChoiceField(label="Batch", queryset=Program.objects.none(), required=False, empty_label="All batches")

    def __init__(self, *args, show_batch=True, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["batch"].queryset = Program.objects.filter(is_active=True).order_by("name")
        if not show_batch:
            del self.fields["batch"]

    def clean_date(self):
        day = self.cleaned_data["date"]
        if day > timezone.localdate():
            raise forms.ValidationError("Attendance cannot be marked for a future date.")
        return day


class AttendanceReportForm(forms.Form):
    VIEWS = [("records", "Daily records"), ("summary", "Summary (counts and %)")]
    view = forms.ChoiceField(label="Report", choices=VIEWS, required=False)
    month = forms.CharField(label="Month", required=False, widget=forms.DateInput(attrs={"type": "month"}))
    date_from = forms.DateField(label="From (range)", required=False, widget=forms.DateInput(attrs={"type": "date"}))
    date_to = forms.DateField(label="To (range)", required=False, widget=forms.DateInput(attrs={"type": "date"}))
    batch = forms.ModelChoiceField(label="Batch", queryset=Program.objects.none(), required=False, empty_label="All batches")
    who = forms.CharField(label="Student ID / Staff username", required=False, max_length=150)
    status = forms.ChoiceField(label="Status", required=False, choices=[("", "All")] + list(Status.choices))

    def __init__(self, *args, staff=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["batch"].queryset = Program.objects.filter(is_active=True).order_by("name")
        if staff:
            del self.fields["batch"]
            self.fields["who"].label = "Staff username"
        else:
            self.fields["who"].label = "Student ID"
