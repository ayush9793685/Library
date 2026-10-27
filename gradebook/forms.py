from django import forms

from academics.models import Course

from .models import Exam


class ExamForm(forms.ModelForm):
    course_code = forms.ChoiceField(label="Course")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        courses = Course.objects.filter(status=Course.Status.ACTIVE).order_by("code")
        self.fields["course_code"].choices = [("", "Select course")] + [
            (course.code, f"{course.code} - {course.name}") for course in courses
        ]
        for field in self.fields.values():
            field.widget.attrs.update(
                {
                    "class": "w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm outline-none transition focus:border-slate-600 focus:ring-2 focus:ring-slate-200",
                }
            )

    class Meta:
        model = Exam
        fields = ["title", "course_code", "assessment_type", "total_marks", "exam_date", "is_published"]
        widgets = {"exam_date": forms.DateInput(attrs={"type": "date"})}


class BulkGradeForm(forms.Form):
    payload = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 10, "placeholder": "STU-0001,87.5"}),
        help_text="One record per line: student_id,marks_obtained",
    )
