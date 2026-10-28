import hmac

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model
from django.utils.crypto import get_random_string
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q
from django.http import FileResponse, Http404, HttpResponseForbidden, HttpResponseRedirect
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from fees.models import Payment
from helpdesk.models import Ticket
from notifications_center.models import Notification
from registration.models import CourseRegistration

from audits.utils import create_audit_log

from academics.forms import QuickProgramForm
from academics.models import Program

from . import seats
from .forms import AddressForm, ContactInformationForm, EmergencyContactForm, SeatUnavailable, StudentForm
from .forms import ADMIN_ONLY_FIELDS
from .models import Address, ContactInformation, EmergencyContact, Student

User = get_user_model()


import logging  # noqa: E402

logger = logging.getLogger(__name__)


def _guess_type(name):
    import mimetypes

    return mimetypes.guess_type(name)[0] or "application/octet-stream"


def _is_admin(user):
    return user.is_authenticated and (user.is_staff or user.role == "admin")


def _build_unique_username(base_username):
    username = base_username
    counter = 1
    while User.objects.filter(username=username).exists():
        username = f"{base_username}{counter}"
        counter += 1
    return username


@login_required
def student_list(request):
    if not _is_admin(request.user):
        return HttpResponseForbidden("Not allowed")
    qs = Student.objects.select_related("contact", "program", "user").all()
    q = request.GET.get("q", "").strip()
    if q:
        match = (
            Q(student_id__icontains=q)
            | Q(registration_number__icontains=q)
            | Q(first_name__icontains=q)
            | Q(last_name__icontains=q)
            | Q(contact__primary_email__icontains=q)
            | Q(program__name__icontains=q)
            | Q(rfid_uid__icontains=q)
            | Q(aadhaar_last4=q)
        )
        if q.isdigit():
            match |= Q(seat_number=int(q))
        qs = qs.filter(match)
    status = request.GET.get("status", "").strip()
    program = request.GET.get("program", "").strip()

    if status:
        qs = qs.filter(status=status)
    if program:
        qs = qs.filter(program_id=program)
    qs = qs.distinct().order_by("student_id")
    paginator = Paginator(qs, 15)
    page_obj = paginator.get_page(request.GET.get("page"))
    for st in page_obj.object_list:
        st.pay_status = st.payment_status

    return render(
        request,
        "students/student_list.html",
        {
            "students": page_obj.object_list,
            "page_obj": page_obj,
            "program_options": Program.objects.filter(is_active=True).order_by("name"),
            "seats_used": Student.objects.filter(seat_number__isnull=False).count(),
            "total_seats": seats.total_seats(),
        },
    )


@login_required
def program_quick_add(request):
    if not _is_admin(request.user):
        return HttpResponseForbidden("Not allowed")
    messages.info(request, "Batches (with fee and timings) are managed under Batches & Seats.")
    return redirect("academics:index")


@login_required
def student_detail(request, pk):
    student = get_object_or_404(Student.objects.select_related("contact", "program", "emergency_contact", "user"), pk=pk)
    is_admin = _is_admin(request.user)
    if not is_admin and request.user != student.user:
        return HttpResponseForbidden("Not allowed")
    payments = student.payments.filter(is_cancelled=False).order_by("-paid_on", "-id")[:6]
    return render(request, "students/student_detail.html", {
        "student": student, "is_admin": is_admin,
        "payment_status": student.payment_status, "recent_payments": payments,
    })


@login_required
def my_profile(request):
    if _is_admin(request.user):
        return redirect("dashboard:home")
    student = get_object_or_404(Student.objects.select_related("program"), user=request.user)
    return render(request, "students/student_detail.html", {
        "student": student, "is_admin": False, "payment_status": student.payment_status,
        "recent_payments": student.payments.filter(is_cancelled=False).order_by("-paid_on", "-id")[:6],
    })


def _form_context(form, title):
    return {"form": form, "title": title, "batch_info": form.batch_info, "is_new": form.is_new}


@login_required
def student_create(request):
    if not _is_admin(request.user):
        return HttpResponseForbidden("Not allowed")
    if request.method == "POST":
        form = StudentForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                student, payment = form.save_all(user=request.user)
            except SeatUnavailable as exc:
                form.add_error("seat_number", str(exc))
            else:
                msg = f"Student created. Seat {student.seat_number}."
                if payment:
                    msg += f" Receipt {payment.receipt_number} recorded."
                messages.success(request, msg)
                if payment:
                    return redirect("fees:receipt", pk=payment.pk)
                return redirect("students:detail", pk=student.pk)
    else:
        form = StudentForm()
    return render(request, "students/student_form.html", _form_context(form, "Add Student"))


@login_required
def student_edit(request, pk):
    student = get_object_or_404(Student, pk=pk)
    is_admin = _is_admin(request.user)
    if not is_admin and request.user != student.user:
        return HttpResponseForbidden("Not allowed")

    old_student_id = student.student_id

    form = StudentForm(request.POST or None, request.FILES or None, instance=student)

    if not is_admin:
        for field_name in ADMIN_ONLY_FIELDS:
            if field_name in form.fields:
                form.fields[field_name].disabled = True

    if request.method == "POST" and form.is_valid():
        try:
            student, _ = form.save_all(user=request.user)
        except SeatUnavailable as exc:
            form.add_error("seat_number", str(exc))
        else:
            student.refresh_from_db()
            new_student_id = student.student_id
            if new_student_id != old_student_id:
                Payment.objects.filter(student_id_text=old_student_id).update(student_id_text=new_student_id)
                CourseRegistration.objects.filter(student_id_text=old_student_id).update(student_id_text=new_student_id)
                Ticket.objects.filter(student_id_text=old_student_id).update(student_id_text=new_student_id)
                Notification.objects.filter(student_id_text=old_student_id).update(student_id_text=new_student_id)
                create_audit_log(user=request.user, action="student_id_change", object_modified=f"{old_student_id} -> {new_student_id}")
            create_audit_log(user=request.user, action="profile_update", object_modified=new_student_id)
            messages.success(request, "Profile updated")
            return redirect("students:detail", pk=student.pk)
    return render(request, "students/student_form.html", _form_context(form, "Edit Student"))


@login_required
def student_delete(request, pk):
    """Permanently delete a student with everything attached (payments, attendance, Aadhaar copy)."""
    if not _is_admin(request.user):
        return HttpResponseForbidden("Not allowed")
    student = get_object_or_404(Student, pk=pk)
    payments = student.payments.count()
    attendance = student.attendance_records.count()
    error = ""
    if request.method == "POST":
        typed = "".join(request.POST.get("confirm_id", "").split()).strip("()").upper()
        if typed != "".join(str(student.student_id).split()).upper():
            error = "Type the student ID exactly to confirm."
        elif request.POST.get("password", "") != str(settings.DELETE_PASSWORD):
            error = "Wrong password."
            create_audit_log(user=request.user, action="student_delete_wrong_password", object_modified=student.student_id)
        else:
            sid, name = student.student_id, f"{student.first_name} {student.last_name}".strip()
            copy = student.aadhaar_copy
            with transaction.atomic():
                seats.lock_seat_rows()
                student.delete()
            if copy:
                try:
                    copy.storage.delete(copy.name)
                except Exception:
                    pass
            create_audit_log(
                user=request.user, action="student_deleted", object_modified=sid,
                old_value=f"{name}; {payments} payments, {attendance} attendance rows removed",
            )
            messages.success(request, f"Student {sid} and all related records were deleted permanently.")
            return redirect("students:list")
    return render(request, "students/student_confirm_delete.html", {
        "student": student, "payments": payments, "attendance": attendance, "error": error,
    })


@login_required
def student_deactivate(request, pk):
    """Permanent deactivation requested by an admin: frees the seat and disables the RFID card for good."""
    if not _is_admin(request.user):
        return HttpResponseForbidden("Not allowed")
    student = get_object_or_404(Student, pk=pk)
    if student.status == Student.Status.DEACTIVATED:
        messages.info(request, "This student is already deactivated.")
        return redirect("students:detail", pk=student.pk)
    error = ""
    if request.method == "POST":
        reason = request.POST.get("reason", "").strip()
        if not reason:
            error = "Please give a reason."
        elif request.POST.get("confirm") != "yes":
            error = "Please tick the box to confirm."
        else:
            with transaction.atomic():
                seats.lock_seat_rows()
                student.released_seat = student.seat_number
                student.seat_number = None
                student.status = Student.Status.DEACTIVATED
                student.deactivated_at = timezone.now()
                student.deactivated_by = request.user
                student.deactivation_reason = reason[:255]
                student.save()
            create_audit_log(
                user=request.user, action="student_deactivated", object_modified=student.student_id,
                old_value=f"seat {student.released_seat}, card {student.rfid_uid or '-'}", new_value=reason[:200],
            )
            messages.success(request, f"{student.student_id} deactivated. Seat {student.released_seat or '-'} is free and the RFID card is disabled permanently.")
            return redirect("students:detail", pk=student.pk)
    return render(request, "students/student_deactivate.html", {"student": student, "error": error})


@login_required
def seat_overview(request):
    if not _is_admin(request.user):
        return HttpResponseForbidden("Not allowed")
    rows = seats.seat_map()
    full = sum(1 for r in rows if r["full"])
    half_seats = sum(1 for r in rows if (r["morning"] or r["afternoon"]))
    empty = sum(1 for r in rows if not (r["full"] or r["morning"] or r["afternoon"]))
    return render(request, "students/seat_map.html", {
        "rows": rows, "total_seats": seats.total_seats(),
        "full_count": full, "half_count": half_seats, "empty_count": empty,
        "morning_free": len(seats.free_seats("morning")),
        "afternoon_free": len(seats.free_seats("afternoon")),
        "full_free": len(seats.free_seats("full_day")),
    })


@login_required
def seat_change(request, pk):
    """Move a student to a different seat (the seat stays fixed afterwards)."""
    if not _is_admin(request.user):
        return HttpResponseForbidden("Not allowed")
    student = get_object_or_404(Student.objects.select_related("program"), pk=pk)
    if student.status == Student.Status.DEACTIVATED or not student.program_id:
        messages.error(request, "This student cannot be given a seat.")
        return redirect("students:detail", pk=student.pk)
    shift = student.program.shift
    options = seats.free_seats(shift, exclude_pk=student.pk)
    error = ""
    if request.method == "POST":
        try:
            target = int(request.POST.get("seat", ""))
        except ValueError:
            target = 0
        with transaction.atomic():
            seats.lock_seat_rows()
            if target and seats.seat_is_free(target, shift, student.pk):
                old = student.seat_number
                student.seat_number = target
                student.seat_shift = shift
                student.save()
                create_audit_log(user=request.user, action="seat_change", object_modified=student.student_id,
                                 old_value=f"seat {old}", new_value=f"seat {target}")
                messages.success(request, f"Seat changed to {target}.")
                return redirect("students:detail", pk=student.pk)
        error = "That seat is not free for this student's timings."
        options = seats.free_seats(shift, exclude_pk=student.pk)
    return render(request, "students/seat_change.html", {"student": student, "options": options, "error": error})


def _aadhaar_lock_state(request, student):
    key = f"aadhaar_fail_{student.pk}"
    data = request.session.get(key, {"n": 0, "until": 0})
    now = timezone.now().timestamp()
    if data.get("until", 0) > now:
        return key, data, int(data["until"] - now)
    if data.get("until", 0) and data["until"] <= now:
        data = {"n": 0, "until": 0}
        request.session[key] = data
    return key, data, 0


@login_required
def aadhaar_copy_view(request, pk):
    """Open the Aadhaar copy: admin login + the Aadhaar password, with lock-out and an audit entry."""
    if not _is_admin(request.user):
        return HttpResponseForbidden("Not allowed")
    student = get_object_or_404(Student, pk=pk)
    if not student.aadhaar_copy:
        raise Http404("No Aadhaar copy on file.")
    key, data, locked_for = _aadhaar_lock_state(request, student)
    error = ""
    if locked_for:
        error = f"Too many wrong attempts. Try again in {locked_for // 60 + 1} minute(s)."
    elif request.method == "POST":
        supplied = request.POST.get("password", "")
        expected = str(getattr(settings, "AADHAAR_VIEW_PASSWORD", ""))
        if expected and hmac.compare_digest(supplied.encode(), expected.encode()):
            request.session.pop(key, None)
            create_audit_log(user=request.user, action="aadhaar_copy_viewed", object_modified=student.student_id)
            copy = student.aadhaar_copy
            try:
                handle = copy.open("rb")
            except NotImplementedError:
                handle = None
            except Exception:
                logger.exception("Could not read the Aadhaar copy of %s directly", student.student_id)
                handle = None
            if handle is not None:
                response = FileResponse(handle, content_type=_guess_type(copy.name))
                response["Cache-Control"] = "no-store"
                response["X-Content-Type-Options"] = "nosniff"
                return response
            try:
                return HttpResponseRedirect(copy.storage.url(copy.name))  # signed, short-lived (Cloudinary)
            except ValueError:
                return render(request, "students/aadhaar_password.html", {
                    "student": student, "error": "The file could not be opened right now. Please try again.",
                })
        data["n"] = data.get("n", 0) + 1
        if data["n"] >= int(getattr(settings, "AADHAAR_VIEW_MAX_ATTEMPTS", 5)):
            data["until"] = timezone.now().timestamp() + int(getattr(settings, "AADHAAR_VIEW_LOCK_SECONDS", 900))
            data["n"] = 0
        request.session[key] = data
        create_audit_log(user=request.user, action="aadhaar_copy_wrong_password", object_modified=student.student_id)
        error = "Wrong password."
    return render(request, "students/aadhaar_password.html", {"student": student, "error": error})
