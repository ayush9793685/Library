from django import forms

from academics.models import Course, Department, Program

from .models import AttendanceRecord, AttendanceSession, Enrollment


class SessionForm(forms.ModelForm):
    department = forms.ModelChoiceField(
        queryset=Department.objects.filter(is_active=True),
        label="Department",
        empty_label="Select department",
    )
    program = forms.ModelChoiceField(
        queryset=Program.objects.filter(is_active=True),
        label="Program",
        empty_label="Select program",
    )
    course = forms.ModelChoiceField(
        queryset=Course.objects.filter(status=Course.Status.ACTIVE),
        label="Course",
        empty_label="Select course",
    )

    class Meta:
        model = AttendanceSession
        fields = [
            "session_date",
            "department",
            "program",
            "semester",
            "course",
            "time_slot",
        ]
        widgets = {
            "session_date": forms.DateInput(attrs={"type": "date"}),
            "semester": forms.TextInput(attrs={"placeholder": "e.g. 2026-1"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if "department" in self.data:
            try:
                department_id = int(self.data.get("department"))
                self.fields["program"].queryset = self.fields["program"].queryset.filter(department_id=department_id)
                self.fields["course"].queryset = self.fields["course"].queryset.filter(department_id=department_id)
            except (TypeError, ValueError):
                pass
        elif self.instance.pk and self.instance.department_id:
            self.fields["program"].queryset = self.fields["program"].queryset.filter(department=self.instance.department)
            self.fields["course"].queryset = self.fields["course"].queryset.filter(department=self.instance.department)
        self.fields["department"].widget.attrs.update({"data-filter": "program"})
        self.fields["program"].widget.attrs.update({"data-department": "department"})

    def clean(self):
        cleaned_data = super().clean()
        department = cleaned_data.get("department")
        program = cleaned_data.get("program")
        course = cleaned_data.get("course")
        if department and program and program.department_id != department.id:
            self.add_error("program", "Select a program that belongs to the selected department.")
        if department and course and course.department_id != department.id:
            self.add_error("course", "Select a course that belongs to the selected department.")
        return cleaned_data

    def save(self, commit=True):
        session = super().save(commit=False)
        if session.course and session.course.instructor:
            session.instructor = session.course.instructor
            session.instructor_name = session.course.instructor.full_name
        if commit:
            session.save()
            self.save_m2m()
        return session


class AttendanceRecordForm(forms.ModelForm):
    class Meta:
        model = AttendanceRecord
        fields = ["status", "remarks"]
        widgets = {
            "status": forms.Select(attrs={"class": "status-select"}),
            "remarks": forms.TextInput(attrs={"placeholder": "Optional remarks", "class": "text-sm"}),
        }


class BulkAttendanceForm(forms.Form):
    payload = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 10, "placeholder": "STU-0001,present,On time"}),
        help_text="One record per line: student_id,status,remarks(optional)",
    )
