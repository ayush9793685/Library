from django.db import models


class Exam(models.Model):
    class AssessmentType(models.TextChoices):
        QUIZ = "quiz", "Quiz"
        ASSIGNMENT = "assignment", "Assignment"
        MIDTERM = "midterm", "Midterm"
        FINAL = "final", "Final Exam"

    title = models.CharField(max_length=150)
    course_code = models.CharField(max_length=20, db_index=True)
    assessment_type = models.CharField(max_length=20, choices=AssessmentType.choices)
    total_marks = models.PositiveIntegerField()
    exam_date = models.DateField()
    is_published = models.BooleanField(default=False)


class GradeRecord(models.Model):
    exam = models.ForeignKey(Exam, on_delete=models.CASCADE, related_name="grades")
    student_id = models.CharField(max_length=30, db_index=True)
    marks_obtained = models.DecimalField(max_digits=6, decimal_places=2)
    letter_grade = models.CharField(max_length=4, blank=True)
    grade_points = models.DecimalField(max_digits=4, decimal_places=2, default=0)

    class Meta:
        unique_together = ("exam", "student_id")

# Create your models here.
