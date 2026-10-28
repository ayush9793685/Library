from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q, Sum
from django.shortcuts import redirect, render

from academics.models import Program
from audits.models import AuditLog
from fees.models import Payment
from helpdesk.models import Ticket
from notifications_center.models import Notification
from registration.models import CourseRegistration
from students.models import Student


def landing(request):
    if request.user.is_authenticated:
        return redirect("dashboard:home")
    return render(request, "home.html")


@login_required
def home(request):
    if request.user.is_staff or request.user.role == "admin":
        total = Student.objects.count()
        active = Student.objects.filter(status=Student.Status.ACTIVE).count()
        inactive = Student.objects.filter(status=Student.Status.INACTIVE).count()
        deactivated = Student.objects.filter(status=Student.Status.DEACTIVATED).count()
        by_program = list(Student.objects.values("program__name").annotate(total=Count("id")).order_by("program__name"))
        by_year = list(Student.objects.values("academic_year").annotate(total=Count("id")).order_by("academic_year"))
        recent = Student.objects.select_related("program").order_by("-created_at")[:5]
        updates = AuditLog.objects.filter(action__in=["profile_update", "student_create"]).select_related("user")[:10]
        module_stats = {
            "programs": Program.objects.filter(is_active=True).count(),
            "open_tickets": Ticket.objects.filter(status=Ticket.Status.OPEN).count(),
            "resolved_tickets": Ticket.objects.filter(status=Ticket.Status.RESOLVED).count(),
        }
        return render(
            request,
            "dashboard/admin_dashboard.html",
            {
                "total": total,
                "active": active,
                "inactive": inactive,
                "deactivated": deactivated,
                "by_program": by_program,
                "by_year": by_year,
                "recent": recent,
                "updates": updates,
                "module_stats": module_stats,
            },
        )

    student = request.user.student_profile

    fields = [
        student.student_id,
        student.first_name,
        student.last_name,
        student.registration_number,
        student.program,
        student.academic_year,
    ]
    completion = int((sum(bool(f) for f in fields) / len(fields)) * 100)

    activity = AuditLog.objects.filter(user=request.user)[:10]

    # One monthly fee (batch fee or custom). Nothing is due while the plan is paid up.
    expected_fees = student.monthly_fee
    paid_fees = Payment.objects.filter(student=student, is_cancelled=False).aggregate(total=Sum("amount_paid"))["total"] or Decimal("0")
    outstanding_fees = Decimal("0") if student.payment_status in ("Paid", "Deactivated") else expected_fees

    active_registrations = CourseRegistration.objects.filter(
        student=student,
        status=CourseRegistration.Status.APPROVED,
    ).count()

    open_tickets = Ticket.objects.filter(
        student=student,
        status__in=[Ticket.Status.OPEN, Ticket.Status.IN_PROGRESS],
    ).count()

    unread_notifications = Notification.objects.filter(student=student, is_read=False).count()

    return render(request, "dashboard/student_dashboard.html", {
        "student": student,
        "completion": completion,
        "activity": activity,
        "expected_fees": expected_fees,
        "paid_fees": paid_fees,
        "outstanding_fees": outstanding_fees,
        "active_registrations": active_registrations,
        "open_tickets": open_tickets,
        "unread_notifications": unread_notifications,
    })

# Create your views here.