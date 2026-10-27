from django import forms

from .models import Department, Program


class ProgramForm(forms.ModelForm):
    class Meta:
        model = Program
        fields = ["name", "code", "duration_semesters", "is_active"]

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
