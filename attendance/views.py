import csv
from collections import defaultdict

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.http import HttpResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render

from students.models import Student

from .forms import AttendanceRecordForm, SessionForm
from .models import AttendanceRecord, AttendanceSession, Enrollment


def _is_admin(user):
    return user.is_authenticated and (user.is_staff or user.role == "admin")


def _sync_session_enrollments(session):
    students_qs = Student.objects.select_related("department", "program").filter(
        status=Student.Status.ACTIVE
    )
    if session.department_id:
        students_qs = students_qs.filter(department_id=session.department_id)
    if session.program_id:
        students_qs = students_qs.filter(program_id=session.program_id)
    if session.semester:
        students_qs = students_qs.filter(semester=session.semester)

    created = 0
    for student in students_qs.order_by("student_id"):
        _, was_created = Enrollment.objects.get_or_create(
            course=session.course,
            student_id=student.student_id,
        )
        if was_created:
            created += 1
    return created


@login_required
def index(request):
    if _is_admin(request.user):
        sessions = AttendanceSession.objects.annotate(
            total=Count("records")
        ).select_related("course").order_by("-session_date")[:50]

        report = AttendanceRecord.objects.values("status").annotate(
            total=Count("id")
        ).order_by("status")

        monthly = defaultdict(lambda: {"total": 0, "present_like": 0})
        low_attendance = []

        student_records = AttendanceRecord.objects.values(
            "student_id", "status"
        ).order_by("student_id")
        per_student = defaultdict(lambda: {"total": 0, "present_like": 0})
        for row in student_records:
            sid = row["student_id"]
            per_student[sid]["total"] += 1
            if row["status"] in [
                AttendanceRecord.Status.PRESENT,
                AttendanceRecord.Status.LATE,
                AttendanceRecord.Status.EXCUSED,
            ]:
                per_student[sid]["present_like"] += 1
        for sid, data in per_student.items():
            pct = (data["present_like"] / data["total"] * 100) if data["total"] else 0
            if pct < 75:
                low_attendance.append(
                    {"student_id": sid, "percentage": round(pct, 2)}
                )

        for row in (
            AttendanceRecord.objects.select_related("session")
            .values("session__session_date", "status")
        ):
            month_key = row["session__session_date"].strftime("%Y-%m")
            monthly[month_key]["total"] += 1
            if row["status"] in [
                AttendanceRecord.Status.PRESENT,
                AttendanceRecord.Status.LATE,
                AttendanceRecord.Status.EXCUSED,
            ]:
                monthly[month_key]["present_like"] += 1

        trend_labels = sorted(monthly.keys())
        trend_values = [
            round((monthly[m]["present_like"] / monthly[m]["total"] * 100), 2)
            if monthly[m]["total"]
            else 0
            for m in trend_labels
        ]

        return render(
            request,
            "attendance/index.html",
            {
                "sessions": sessions,
                "report": report,
                "is_admin": True,
                "low_attendance": low_attendance[:15],
                "trend_labels": trend_labels,
                "trend_values": trend_values,
            },
        )

    student = get_object_or_404(Student, user=request.user)
    records = (
        AttendanceRecord.objects.filter(student_id=student.student_id)
        .select_related("session", "session__course")
        .order_by("-session__session_date")
    )
    total = records.count()
    present_like = records.filter(
        status__in=[
            AttendanceRecord.Status.PRESENT,
            AttendanceRecord.Status.LATE,
            AttendanceRecord.Status.EXCUSED,
        ]
    ).count()
    percentage = round((present_like / total) * 100, 2) if total else 0
    by_course = (
        records.values("session__course__code", "session__course__name")
        .annotate(
            total=Count("id"),
            present=Count("id", filter=Q(status=AttendanceRecord.Status.PRESENT)),
        )
    )
    return render(
        request,
        "attendance/student_view.html",
        {
            "records": records[:100],
            "attendance_percentage": percentage,
            "by_course": by_course,
        },
    )


@login_required
def session_create(request):
    if not _is_admin(request.user):
        return HttpResponseForbidden("Not allowed")
    form = SessionForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        session = form.save()
        created = _sync_session_enrollments(session)
        messages.success(request, "Attendance session created.")
        if created:
            messages.info(request, f"Enrolled {created} matching students for attendance.")
        return redirect("attendance:mark", pk=session.pk)
    return render(
        request, "attendance/form.html", {"form": form, "title": "Create Attendance Session"}
    )


@login_required
def mark_attendance(request, pk):
    if not _is_admin(request.user):
        return HttpResponseForbidden("Not allowed")
    session = get_object_or_404(
        AttendanceSession.objects.select_related("course"), pk=pk
    )

    _sync_session_enrollments(session)

    enrolled = Enrollment.objects.filter(course=session.course).select_related(
        "course"
    )
    existing = {
        r.student_id: r
        for r in session.records.all()
    }

    if request.method == "POST":
        forms_data = {}
        for key, value in request.POST.items():
            if key.startswith("status_"):
                sid = key.replace("status_", "")
                forms_data[sid] = {
                    "status": value,
                    "remarks": request.POST.get(f"remarks_{sid}", ""),
                }
        created = 0
        for sid, data in forms_data.items():
            if data["status"] not in {c[0] for c in AttendanceRecord.Status.choices}:
                continue
            AttendanceRecord.objects.update_or_create(
                session=session,
                student_id=sid,
                defaults={
                    "status": data["status"],
                    "remarks": data["remarks"],
                },
            )
            created += 1
        messages.success(request, f"Saved {created} attendance records.")
        return redirect("attendance:index")

    enrolled_students = []
    students = {
        student.student_id: student
        for student in Student.objects.filter(
            student_id__in=[e.student_id for e in enrolled]
        )
    }
    for e in enrolled:
        record = existing.get(e.student_id)
        enrolled_students.append(
            {
                "enrollment": e,
                "student": students.get(e.student_id),
                "record": record,
                "form": AttendanceRecordForm(
                    initial={
                        "status": record.status if record else AttendanceRecord.Status.PRESENT,
                        "remarks": record.remarks if record else "",
                    }
                ),
            }
        )

    return render(
        request,
        "attendance/mark.html",
        {
            "session": session,
            "enrolled_students": enrolled_students,
        },
    )


@login_required
def mark_all_present(request, pk):
    if not _is_admin(request.user):
        return HttpResponseForbidden("Not allowed")
    session = get_object_or_404(AttendanceSession, pk=pk)
    _sync_session_enrollments(session)
    enrolled = Enrollment.objects.filter(course=session.course)
    count = 0
    for e in enrolled:
        AttendanceRecord.objects.update_or_create(
            session=session,
            student_id=e.student_id,
            defaults={"status": AttendanceRecord.Status.PRESENT, "remarks": ""},
        )
        count += 1
    messages.success(request, f"Marked {count} students present.")
    return redirect("attendance:mark", pk=pk)


@login_required
def session_list(request):
    if not _is_admin(request.user):
        return HttpResponseForbidden("Not allowed")
    sessions = AttendanceSession.objects.annotate(
        total=Count("records")
    ).select_related("course").order_by("-session_date")
    return render(request, "attendance/session_list.html", {"sessions": sessions})


@login_required
def session_delete(request, pk):
    if not _is_admin(request.user):
        return HttpResponseForbidden("Not allowed")
    session = get_object_or_404(AttendanceSession.objects.select_related("course"), pk=pk)
    if request.method == "POST":
        label = f"{session.course.code} on {session.session_date}"
        session.delete()
        messages.success(request, f"Deleted attendance session: {label}.")
        return redirect("attendance:session_list")
    return render(request, "attendance/session_confirm_delete.html", {"session": session})


@login_required
def export_attendance_csv(request):
    if not _is_admin(request.user):
        return HttpResponseForbidden("Not allowed")
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="attendance_report.csv"'
    writer = csv.writer(response)
    writer.writerow(
        ["Date", "Course", "Student ID", "Status", "Remarks", "Department", "Semester", "Time Slot"]
    )
    records = (
        AttendanceRecord.objects.select_related("session", "session__course")
        .order_by("-session__session_date", "student_id")
    )
    for r in records:
        writer.writerow(
            [
                r.session.session_date,
                r.session.course.code,
                r.student_id,
                r.status,
                r.remarks,
                r.session.department.name if r.session.department else "",
                r.session.semester,
                r.session.get_time_slot_display(),
            ]
        )
    return response


@login_required
def export_attendance_excel(request):
    if not _is_admin(request.user):
        return HttpResponseForbidden("Not allowed")
    response = HttpResponse(content_type="application/vnd.ms-excel")
    response["Content-Disposition"] = 'attachment; filename="attendance_report.xls"'
    rows = ["Date\tCourse\tStudent ID\tStatus\tRemarks\tDepartment\tSemester\tTime Slot"]
    records = (
        AttendanceRecord.objects.select_related("session", "session__course", "session__department")
        .order_by("-session__session_date", "student_id")
    )
    for r in records:
        rows.append(
            f"{r.session.session_date}\t{r.session.course.code}\t{r.student_id}\t"
            f"{r.status}\t{r.remarks}\t{r.session.department.name if r.session.department else ''}\t"
            f"{r.session.semester}\t{r.session.get_time_slot_display()}"
        )
    response.write("\n".join(rows))
    return response


@login_required
def attendance_pdf_view(request):
    if not _is_admin(request.user):
        return HttpResponseForbidden("Not allowed")
    records = (
        AttendanceRecord.objects.select_related("session", "session__course")
        .order_by("-session__session_date", "student_id")[:500]
    )
    return render(request, "attendance/report_pdf.html", {"records": records})
