import csv
from collections import defaultdict
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count
from django.http import HttpResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render

from academics.models import Course
from registration.models import CourseRegistration
from students.models import Student

from .forms import BulkGradeForm, ExamForm
from .models import Exam, GradeRecord


def _is_admin(user):
    return user.is_authenticated and (user.is_staff or user.role == "admin")


def _grade_from_percentage(percentage):
    if percentage >= 80:
        return "A+", Decimal("4.00")
    if percentage >= 75:
        return "A", Decimal("3.75")
    if percentage >= 70:
        return "A-", Decimal("3.50")
    if percentage >= 65:
        return "B+", Decimal("3.25")
    if percentage >= 60:
        return "B", Decimal("3.00")
    if percentage >= 55:
        return "B-", Decimal("2.75")
    if percentage >= 50:
        return "C+", Decimal("2.50")
    if percentage >= 45:
        return "C", Decimal("2.25")
    if percentage >= 40:
        return "D", Decimal("2.00")
    return "F", Decimal("0.00")


@login_required
def index(request):
    if _is_admin(request.user):
        exams = Exam.objects.annotate(total_entries=Count("grades")).order_by("-exam_date")
        return render(request, "gradebook/index.html", {"exams": exams, "is_admin": True})
    return redirect("gradebook:my_results")


@login_required
def exam_create(request):
    if not _is_admin(request.user):
        return HttpResponseForbidden("Not allowed")
    form = ExamForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Exam created.")
        return redirect("gradebook:index")
    return render(request, "gradebook/form.html", {"form": form, "title": "Create Exam"})


@login_required
def exam_edit(request, pk):
    if not _is_admin(request.user):
        return HttpResponseForbidden("Not allowed")
    exam = get_object_or_404(Exam, pk=pk)
    form = ExamForm(request.POST or None, instance=exam)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Exam updated.")
        return redirect("gradebook:index")
    return render(request, "gradebook/form.html", {"form": form, "title": "Edit Exam"})


@login_required
def publish_exam(request, pk):
    if not _is_admin(request.user):
        return HttpResponseForbidden("Not allowed")
    exam = get_object_or_404(Exam, pk=pk)
    exam.is_published = True
    exam.save(update_fields=["is_published"])
    messages.success(request, "Results published.")
    return redirect("gradebook:index")


@login_required
def grade_entry(request, pk):
    if not _is_admin(request.user):
        return HttpResponseForbidden("Not allowed")
    exam = get_object_or_404(Exam, pk=pk)

    enrolled_students = Student.objects.filter(
        course_registrations__offering__course__code=exam.course_code,
        course_registrations__status=CourseRegistration.Status.APPROVED,
    ).distinct().order_by("student_id")

    if request.method == "POST":
        saved = 0
        for key, value in request.POST.items():
            if not key.startswith("marks_") or not value.strip():
                continue
            student_id = key[6:]
            try:
                marks = Decimal(value)
            except Exception:
                continue
            if marks < 0 or marks > exam.total_marks:
                continue
            percentage = (marks / Decimal(exam.total_marks)) * Decimal("100")
            letter, points = _grade_from_percentage(float(percentage))
            GradeRecord.objects.update_or_create(
                exam=exam,
                student_id=student_id,
                defaults={"marks_obtained": marks, "letter_grade": letter, "grade_points": points},
            )
            saved += 1
        if saved:
            messages.success(request, f"Saved {saved} grade records.")
        else:
            messages.warning(request, "No valid marks were submitted.")
        return redirect("gradebook:grade_entry", pk=pk)

    existing_grades = {g.student_id: g for g in exam.grades.all()}
    students_data = []
    for s in enrolled_students:
        grade = existing_grades.get(s.student_id)
        students_data.append({
            "student": s,
            "marks": grade.marks_obtained if grade else None,
        })

    grades = exam.grades.order_by("student_id")
    return render(request, "gradebook/grade_entry.html", {
        "exam": exam,
        "grades": grades,
        "students_data": students_data,
    })


@login_required
def my_results(request):
    students = None
    is_admin_view = False

    if _is_admin(request.user):
        student_pk = request.GET.get("student_id", "").strip()
        if not student_pk:
            students = Student.objects.select_related("department", "program").order_by("student_id")
            return render(request, "gradebook/student_results.html", {
                "students": students,
                "is_admin_view": True,
                "rows": [],
                "gpa": 0, "cgpa": 0, "semester_history": [],
            })
        student = get_object_or_404(Student, pk=student_pk)
        students = Student.objects.select_related("department", "program").order_by("student_id")
        is_admin_view = True
        grades = GradeRecord.objects.filter(student_id=student.student_id, exam__is_published=True).select_related("exam")
    else:
        student = get_object_or_404(Student, user=request.user)
        grades = GradeRecord.objects.filter(student_id=student.student_id, exam__is_published=True).select_related("exam")

    total_weighted = Decimal("0")
    total_credits = Decimal("0")
    rows = []
    semester_map = defaultdict(lambda: {"weighted": Decimal("0"), "credits": Decimal("0")})
    for grade in grades:
        course = Course.objects.filter(code=grade.exam.course_code).first()
        credit = Decimal(course.credit_hours) if course else Decimal("0")
        weighted = Decimal(grade.grade_points) * credit
        total_weighted += weighted
        total_credits += credit
        semester_key = course.semester if course else "Unknown"
        semester_map[semester_key]["weighted"] += weighted
        semester_map[semester_key]["credits"] += credit
        rows.append({"grade": grade, "credit": credit})

    gpa = round(total_weighted / total_credits, 2) if total_credits else 0
    semester_history = []
    cumulative_weighted = Decimal("0")
    cumulative_credits = Decimal("0")
    for sem in sorted(semester_map.keys()):
        sem_weighted = semester_map[sem]["weighted"]
        sem_credits = semester_map[sem]["credits"]
        sem_gpa = round(sem_weighted / sem_credits, 2) if sem_credits else 0
        cumulative_weighted += sem_weighted
        cumulative_credits += sem_credits
        sem_cgpa = round(cumulative_weighted / cumulative_credits, 2) if cumulative_credits else 0
        semester_history.append({"semester": sem, "gpa": sem_gpa, "cgpa": sem_cgpa})

    return render(
        request,
        "gradebook/student_results.html",
        {
            "rows": rows, "gpa": gpa, "cgpa": gpa,
            "semester_history": semester_history,
            "student": student, "is_admin_view": is_admin_view,
            "students": students,
        },
    )


@login_required
def export_gradebook_csv(request):
    if not _is_admin(request.user):
        return HttpResponseForbidden("Not allowed")
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="gradebook_report.csv"'
    writer = csv.writer(response)
    writer.writerow(["Exam", "Course", "Student ID", "Marks", "Letter", "Points", "Published"])
    for g in GradeRecord.objects.select_related("exam").order_by("-exam__exam_date", "student_id"):
        writer.writerow([g.exam.title, g.exam.course_code, g.student_id, g.marks_obtained, g.letter_grade, g.grade_points, g.exam.is_published])
    return response


@login_required
def export_gradebook_excel(request):
    if not _is_admin(request.user):
        return HttpResponseForbidden("Not allowed")
    response = HttpResponse(content_type="application/vnd.ms-excel")
    response["Content-Disposition"] = 'attachment; filename="gradebook_report.xls"'
    lines = ["Exam\tCourse\tStudent ID\tMarks\tLetter\tPoints\tPublished"]
    for g in GradeRecord.objects.select_related("exam").order_by("-exam__exam_date", "student_id"):
        lines.append(f"{g.exam.title}\t{g.exam.course_code}\t{g.student_id}\t{g.marks_obtained}\t{g.letter_grade}\t{g.grade_points}\t{g.exam.is_published}")
    response.write("\n".join(lines))
    return response


@login_required
def transcript_pdf_view(request):
    if _is_admin(request.user):
        student_pk = request.GET.get("student_id", "").strip()
        if not student_pk:
            return HttpResponseForbidden("Select a student first.")
        student = get_object_or_404(Student, pk=student_pk)
    else:
        student = get_object_or_404(Student, user=request.user)
    grades = GradeRecord.objects.filter(student_id=student.student_id, exam__is_published=True).select_related("exam")
    return render(request, "gradebook/transcript_pdf.html", {"student": student, "grades": grades})

# Create your views here.
