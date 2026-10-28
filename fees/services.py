"""Recording and cancelling payments, and keeping the student's plan in step."""
from datetime import timedelta
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from audits.utils import create_audit_log
from students.models import Student

from .models import Payment


class PaymentError(Exception):
    pass


def check_can_pay(student, amount=None):
    """Validate a payment before recording it. Raises PaymentError with a clear message."""
    if student.status == Student.Status.DEACTIVATED:
        raise PaymentError("This student is deactivated. Payments cannot be recorded; register again if they return.")
    if not student.program_id:
        raise PaymentError("This student has no batch yet, so the fee is unknown.")
    fee = student.monthly_fee
    if fee <= 0:
        raise PaymentError("The monthly fee for this student is not set.")
    if amount is not None and Decimal(amount) != fee:
        raise PaymentError(f"The fee must be paid in full: Rs. {fee:g} per month for this student.")
    # Block paying the same 30 days twice.
    if student.subscription_end and student.status == Student.Status.ACTIVE:
        limit = timezone.now() + timedelta(days=Student._plan_days())
        if student.subscription_end > limit:
            raise PaymentError("The next 30 days are already paid for this student.")
    return fee


@transaction.atomic
def record_payment(student, *, mode, reference="", paid_on=None, user=None, registration=False):
    """Create a payment for the student's monthly fee and extend the plan.

    registration=True is used for the first month collected at registration: the 30 days
    were already set when the student was created, so the plan is not extended again.
    """
    student = Student.objects.select_for_update().select_related("program").get(pk=student.pk)
    fee = check_can_pay(student) if not registration else student.monthly_fee
    paid_on = paid_on or timezone.localdate()
    previous_end = student.subscription_end
    if registration:
        start = paid_on
        end = timezone.localtime(student.subscription_end).date() if student.subscription_end else paid_on
    else:
        start, end = student.renew_subscription(paid_on)
    payment = Payment.objects.create(
        student=student,
        student_id_text=student.student_id,
        amount_paid=fee,
        paid_on=paid_on,
        payment_mode=mode,
        reference=(reference or "").strip(),
        period_start=start,
        period_end=end,
        extends_plan=not registration,
        previous_plan_end=previous_end,
        recorded_by=user,
    )
    create_audit_log(
        user=user, action="payment_recorded",
        object_modified=f"{payment.receipt_number} {student.student_id}",
        new_value=f"{fee} via {mode}",
    )
    return payment


@transaction.atomic
def cancel_payment(payment, *, reason, user=None):
    """Cancel a receipt (kept for the records) and step the plan back if it was the latest renewal."""
    if payment.is_cancelled:
        raise PaymentError("This receipt is already cancelled.")
    if not reason.strip():
        raise PaymentError("A reason is required to cancel a receipt.")
    student = payment.student
    if student and payment.extends_plan:
        newer = Payment.objects.filter(student=student, is_cancelled=False, extends_plan=True, pk__gt=payment.pk).exists()
        if newer:
            raise PaymentError("Only the latest payment of a student can be cancelled. Cancel the newer receipt first.")
    payment.is_cancelled = True
    payment.cancel_reason = reason.strip()[:255]
    payment.cancelled_at = timezone.now()
    payment.cancelled_by = user
    payment.save(update_fields=["is_cancelled", "cancel_reason", "cancelled_at", "cancelled_by"])
    if student and payment.extends_plan and payment.previous_plan_end:
        # Restore the plan end date from before this payment, then let expiry run as normal.
        student.subscription_end = payment.previous_plan_end
        student.save(update_fields=["subscription_end", "updated_at"])
        Student.expire_overdue()
    create_audit_log(
        user=user, action="payment_cancelled",
        object_modified=f"{payment.receipt_number} {student.student_id if student else ''}",
        old_value=str(payment.amount_paid), new_value=reason[:200],
    )
    return payment


def delete_payment(payment, *, user=None):
    """Permanently remove a payment record. If it is the latest renewal, the plan end date steps back."""
    student = payment.student
    if student and payment.extends_plan and not payment.is_cancelled:
        newer = Payment.objects.filter(student=student, is_cancelled=False, extends_plan=True, pk__gt=payment.pk).exists()
        if newer:
            raise PaymentError("Delete the student's newer payment first, so the plan dates stay correct.")
    label = f"{payment.receipt_number} {student.student_id if student else ''}".strip()
    amount = str(payment.amount_paid)
    with transaction.atomic():
        if student and payment.extends_plan and not payment.is_cancelled and payment.previous_plan_end:
            student.subscription_end = payment.previous_plan_end
            student.save(update_fields=["subscription_end", "updated_at"])
        payment.delete()
        Student.expire_overdue()
    create_audit_log(user=user, action="payment_deleted", object_modified=label, old_value=amount)
