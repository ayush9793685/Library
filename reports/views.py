import csv

from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, HttpResponseForbidden
from django.utils import timezone

from students.models import Student


def _admin(user):
    return user.is_staff or user.role == "admin"


@login_required
def reports_home(request):
    if not _admin(request.user):
        return HttpResponseForbidden("Not allowed")
    return HttpResponse("Reports module: use /reports/students/csv/ for export.")


@login_required
def export_students_csv(request):
    if not _admin(request.user):
        return HttpResponseForbidden("Not allowed")
    today = timezone.localdate()
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = 'attachment; filename="student_directory.csv"'
    response.write("\ufeff")  # lets Excel read names correctly
    writer = csv.writer(response)
    writer.writerow([
        "Student ID", "Name", "Registration No", "Program", "Academic Year",
        "Enrollment Date", "Plan Status", "Plan Valid Until",
        "Phone", "Alternate Phone", "Email",
    ])
    students = Student.objects.select_related("program", "contact").order_by("student_id")
    for s in students.iterator():
        contact = getattr(s, "contact", None)
        name = " ".join(p for p in [s.first_name, s.middle_name, s.last_name] if p)
        plan_active = s.status == "active" and (not s.subscription_end or s.subscription_end >= timezone.now())
        writer.writerow([
            s.student_id,
            name,
            s.registration_number,
            s.program.name if s.program else "",
            s.academic_year,
            s.enrollment_date or "",
            "Active" if plan_active else "Inactive",
            timezone.localtime(s.subscription_end).strftime("%Y-%m-%d %H:%M") if s.subscription_end else "",
            contact.mobile_number if contact else "",
            contact.alternate_mobile_number if contact else "",
            contact.primary_email if contact else "",
        ])
    return response

# Create your views here.