from django import forms

from academics.models import Course

from .models import CourseOffering, RegistrationWindow


class RegistrationWindowForm(forms.ModelForm):
    class Meta:
        model = RegistrationWindow
        fields = ["name", "starts_at", "ends_at", "is_active"]
        widgets = {
            "starts_at": forms.DateTimeInput(attrs={"type": "datetime-local"}),
            "ends_at": forms.DateTimeInput(attrs={"type": "datetime-local"}),
        }


class CourseOfferingForm(forms.ModelForm):
    course = forms.ModelChoiceField(
        queryset=Course.objects.filter(status=Course.Status.ACTIVE).order_by("code"),
        label="Course",
        empty_label="Select course",
    )
    semester = forms.ChoiceField(
        choices=[("", "Select Semester")] + [(str(i), str(i)) for i in range(1, 9)],
    )

    class Meta:
        model = CourseOffering
        fields = ["course", "semester", "capacity", "registration_window"]
