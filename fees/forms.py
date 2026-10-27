from django import forms

from students.models import Student

from .models import FeeStructure, Payment


class FeeStructureForm(forms.ModelForm):
    academic_year = forms.ChoiceField(
        choices=[("", "Select Academic Year")] + [(str(y), str(y)) for y in range(2000, 2036)],
    )

    class Meta:
        model = FeeStructure
        fields = ["fee_type", "amount", "academic_year"]


class PaymentForm(forms.ModelForm):
    student = forms.CharField(
        label="Student ID",
        max_length=30,
        widget=forms.TextInput(attrs={
            "placeholder": "Type student ID",
            "autocomplete": "off",
            "data-student-search": "/fees/students/search/",
        }),
    )

    def clean_student(self):
        student_id = self.cleaned_data["student"].strip()
        student = Student.objects.filter(student_id__iexact=student_id).first()
        if student is None:
            raise forms.ValidationError("No student found with this ID.")
        return student

    class Meta:
        model = Payment
        fields = ["student", "fee_structure", "amount_paid", "paid_on", "reference"]
        widgets = {"paid_on": forms.DateInput(attrs={"type": "date"})}
