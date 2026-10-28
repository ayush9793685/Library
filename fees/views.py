from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q, Sum
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from students.models import Student

from .forms import CancelPaymentForm, PaymentForm
from .models import Payment
from .services import PaymentError, cancel_payment, record_payment


def _is_admin(user):
    return user.is_authenticated and (user.is_staff or user.role == "admin")


def student_fee_summary(student):
    """Fee facts for one student: what they pay monthly and where their plan stands."""
    status = student.payment_status
    fee = student.monthly_fee
    payments = student.payments.filter(is_cancelled=False).order_by("-paid_on", "-id")
    paid_total = payments.aggregate(total=Sum("amount_paid"))["total"] or Decimal("0")
    return {
        "monthly_fee": fee,
        "status": status,
        "paid_total": paid_total,
        # What is still due for the current cycle: nothing while the plan is paid up.
        "balance": Decimal("0") if status == "Paid" else (fee if student.status != Student.Status.DEACTIVATED else Decimal("0")),
        "payments": payments,
    }


@login_required
def index(request):
    if _is_admin(request.user):
        payments = Payment.objects.select_related("student", "student__program").order_by("-paid_on", "-id")[:100]
        today = timezone.localdate()
        month_total = Payment.objects.filter(
            is_cancelled=False, paid_on__year=today.year, paid_on__month=today.month
        ).aggregate(total=Sum("amount_paid"))["total"] or Decimal("0")
        total_collected = Payment.objects.filter(is_cancelled=False).aggregate(total=Sum("amount_paid"))["total"] or Decimal("0")

        students = Student.objects.select_related("program").order_by("student_id")
        selected_student = None
        summary = None
        student_pk = request.GET.get("student_id", "").strip()
        if student_pk:
            selected_student = get_object_or_404(Student.objects.select_related("program"), pk=student_pk)
            summary = student_fee_summary(selected_student)

        return render(request, "fees/admin_index.html", {
            "payments": payments,
            "total_collected": total_collected,
            "month_total": month_total,
            "students": students,
            "selected_student": selected_student,
            "summary": summary,
        })

    student = get_object_or_404(Student.objects.select_related("program"), user=request.user)
    summary = student_fee_summary(student)
    return render(request, "fees/student_index.html", {"student": student, "summary": summary})


@login_required
def payment_create(request):
    if not _is_admin(request.user):
        return HttpResponseForbidden("Not allowed")
    initial = {}
    if request.GET.get("student"):
        initial["student"] = request.GET["student"]
    form = PaymentForm(request.POST or None, initial=initial)
    if request.method == "POST" and form.is_valid():
        try:
            payment = record_payment(
                form.cleaned_data["student"],
                mode=form.cleaned_data["payment_mode"],
                reference=form.cleaned_data["reference"],
                paid_on=form.cleaned_data["paid_on"],
                user=request.user,
            )
        except PaymentError as exc:
            form.add_error("student", str(exc))
        else:
            messages.success(request, f"Payment recorded. Receipt {payment.receipt_number}.")
            return redirect("fees:receipt", pk=payment.pk)
    return render(request, "fees/form.html", {"form": form, "title": "Record Payment"})


@login_required
def receipt(request, pk):
    payment = get_object_or_404(Payment.objects.select_related("student", "student__program"), pk=pk)
    is_admin = _is_admin(request.user)
    if not is_admin and not (payment.student and payment.student.user_id == request.user.id):
        return HttpResponseForbidden("Not allowed")
    return render(request, "fees/receipt.html", {"payment": payment, "is_admin": is_admin})


@login_required
def payment_cancel(request, pk):
    if not _is_admin(request.user):
        return HttpResponseForbidden("Not allowed")
    payment = get_object_or_404(Payment, pk=pk)
    form = CancelPaymentForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            cancel_payment(payment, reason=form.cleaned_data["reason"], user=request.user)
        except PaymentError as exc:
            form.add_error("reason", str(exc))
        else:
            messages.success(request, f"Receipt {payment.receipt_number} cancelled.")
            return redirect("fees:receipt", pk=payment.pk)
    return render(request, "fees/form.html", {"form": form, "title": f"Cancel receipt {payment.receipt_number}"})


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
