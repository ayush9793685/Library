from django import forms
from django.core.validators import RegexValidator

from academics.models import Program

from .models import TrialVisitor


class TrialVisitorForm(forms.ModelForm):
    phone = forms.CharField(
        label="Phone Number", max_length=20,
        validators=[RegexValidator(r"^[0-9+\-() ]+$", "Enter a valid phone number.")],
    )

    class Meta:
        model = TrialVisitor
        fields = ["name", "phone", "trial_date", "program", "notes", "status"]
        widgets = {"trial_date": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d")}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["program"].queryset = Program.objects.filter(is_active=True).order_by("name")
        self.fields["program"].required = False
        self.fields["program"].empty_label = "No preference"
        self.fields["notes"].required = False
        self.fields["trial_date"].input_formats = ["%Y-%m-%d"]
        if not self.instance.pk:
            # A new visitor is always "Visited"; Joined is set only by converting to a student.
            self.fields.pop("status")
        else:
            self.fields["status"].choices = [
                c for c in TrialVisitor.Status.choices
                if c[0] != TrialVisitor.Status.JOINED or self.instance.status == TrialVisitor.Status.JOINED
            ]
