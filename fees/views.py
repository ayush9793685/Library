from decimal import Decimal

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q, Sum
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from students.models import Student

from .forms import FeeStructureForm, PaymentForm
from .models import FeeStructure, Payment


def _is_admin(user):
    return user.is_authenticated and (user.is_staff or user.role == "admin")


def _student_fees(student):
    expected_fees = FeeStructure.objects.filter(academic_year=student.academic_year)
    expected_total = expected_fees.aggregate(total=Sum("amount"))["total"] or Decimal("0")
    payments = Payment.objects.filter(student=student).select_related("fee_structure")
    # Registration is paid once per academic year; library is paid every month,
    # so only this month's library payments count against what is due now.
    today = timezone.localdate()
    due_payments = payments.filter(
        Q(fee_structure__fee_type=FeeStructure.FeeType.REGISTRATION, fee_structure__academic_year=student.academic_year)
        | Q(fee_structure__fee_type=FeeStructure.FeeType.LIBRARY, paid_on__year=today.year, paid_on__month=today.month)
    )
    paid_total = due_payments.aggregate(total=Sum("amount_paid"))["total"] or Decimal("0")
    return expected_fees, expected_total, payments, paid_total


@login_required
def index(request):
    if _is_admin(request.user):
        structures = FeeStructure.objects.order_by("academic_year", "fee_type")
        payments = Payment.objects.select_related("fee_structure", "student").order_by("-paid_on")[:100]
        total_collected = payments.aggregate(total=Sum("amount_paid"))["total"] or Decimal("0")

        students = Student.objects.select_related("department", "program").order_by("student_id")
        selected_student = None
        student_expected_fees = None
        student_expected_total = Decimal("0")
        student_payments = None
        student_paid_total = Decimal("0")
        student_outstanding = Decimal("0")

        student_pk = request.GET.get("student_id", "").strip()
        if student_pk:
            selected_student = get_object_or_404(Student, pk=student_pk)
            student_expected_fees, student_expected_total, student_payments, student_paid_total = _student_fees(selected_student)
            student_outstanding = max(student_expected_total - student_paid_total, Decimal("0"))
            if selected_student.status == Student.Status.INACTIVE:
                student_outstanding = Decimal(str(settings.DEACTIVATED_OUTSTANDING))

        return render(request, "fees/admin_index.html", {
            "structures": structures,
            "payments": payments,
            "total_collected": total_collected,
            "students": students,
            "selected_student": selected_student,
            "student_expected_fees": student_expected_fees,
            "student_expected_total": student_expected_total,
            "student_payments": student_payments,
            "student_paid_total": student_paid_total,
            "student_outstanding": student_outstanding,
        })

    student = get_object_or_404(Student, user=request.user)
    _, expected_total, payments, paid_total = _student_fees(student)
    outstanding = max(expected_total - paid_total, Decimal("0"))
    return render(request, "fees/student_index.html", {
        "payments": payments,
        "paid": paid_total,
        "expected": expected_total,
        "outstanding": outstanding,
    })


@login_required
def structure_create(request):
    if not _is_admin(request.user):
        return HttpResponseForbidden("Not allowed")
    form = FeeStructureForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Fee structure created.")
        return redirect("fees:index")
    return render(request, "fees/form.html", {"form": form, "title": "Create Fee Structure"})


@login_required
def payment_create(request):
    if not _is_admin(request.user):
        return HttpResponseForbidden("Not allowed")
    form = PaymentForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Payment recorded.")
        return redirect("fees:index")
    return render(request, "fees/form.html", {"form": form, "title": "Record Payment"})

# Create your views here.


@login_required
def student_search(request):
    if not _is_admin(request.user):
        return HttpResponseForbidden("Not allowed")
    q = request.GET.get("q", "").strip()
    results = []
    if q:
        matches = Student.objects.filter(
            Q(student_id__istartswith=q) | Q(student_id__icontains=q)
            | Q(first_name__icontains=q) | Q(last_name__icontains=q)
        ).order_by("student_id")[:8]
        results = [
            {"id": s.student_id, "name": " ".join(p for p in [s.first_name, s.middle_name, s.last_name] if p)}
            for s in matches
        ]
    return JsonResponse({"results": results})
