from django import forms

from .models import Department, Program


class ProgramForm(forms.ModelForm):
    class Meta:
        model = Program
        fields = ["name", "code", "monthly_fee", "shift", "start_time", "end_time", "is_active"]
        labels = {"monthly_fee": "Monthly fee (Rs.)", "shift": "Shift (decides seat sharing)"}
        widgets = {
            "start_time": forms.TimeInput(attrs={"type": "time"}, format="%H:%M"),
            "end_time": forms.TimeInput(attrs={"type": "time"}, format="%H:%M"),
        }

    def clean_monthly_fee(self):
        fee = self.cleaned_data["monthly_fee"]
        if fee is None or fee < 0:
            raise forms.ValidationError("Fee cannot be negative.")
        return fee

    def clean(self):
        cleaned = super().clean()
        start, end = cleaned.get("start_time"), cleaned.get("end_time")
        if start and end and end <= start:
            self.add_error("end_time", "End time must be after the start time.")
        return cleaned

    def clean_name(self):
        name = self.cleaned_data["name"].strip()
        clash = Program.objects.filter(name__iexact=name)
        if self.instance.pk:
            clash = clash.exclude(pk=self.instance.pk)
        if clash.exists():
            raise forms.ValidationError("A program with this name already exists.")
        return name

    def save(self, commit=True):
        program = super().save(commit=False)
        if not program.department_id:
            department = Department.objects.filter(code="GEN").first()
            if department is None:
                name = "General"
                if Department.objects.filter(name=name).exists():
                    name = "General (default)"
                department = Department.objects.create(name=name, code="GEN")
            program.department = department
        if commit:
            program.save()
            self.save_m2m()
        return program


class QuickProgramForm(ProgramForm):
    """Name-only form used by the pop-up on the Students page."""

    class Meta:
        model = Program
        fields = ["name"]

    def save(self, commit=True):
        program = super().save(commit=False)
        base = "".join(ch for ch in program.name.upper() if ch.isalnum())[:15] or "PROG"
        code, n = base, 1
        while Program.objects.filter(code=code).exists():
            n += 1
            code = f"{base[:15]}{n}"
        program.code = code
        if commit:
            program.save()
        return program
