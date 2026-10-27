from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model
from django.utils.crypto import get_random_string
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render

from fees.models import Payment
from helpdesk.models import Ticket
from notifications_center.models import Notification
from registration.models import CourseRegistration

from audits.utils import create_audit_log

from academics.forms import QuickProgramForm
from academics.models import Program

from .forms import AddressForm, ContactInformationForm, EmergencyContactForm, StudentForm
from .models import Address, ContactInformation, EmergencyContact, Student

User = get_user_model()


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
        qs = qs.filter(
            Q(student_id__icontains=q)
            | Q(registration_number__icontains=q)
            | Q(first_name__icontains=q)
            | Q(last_name__icontains=q)
            | Q(contact__primary_email__icontains=q)
            | Q(program__name__icontains=q)
        )
    status = request.GET.get("status", "").strip()
    program = request.GET.get("program", "").strip()
    academic_year = request.GET.get("academic_year", "").strip()

    if status:
        qs = qs.filter(status=status)
    if program:
        qs = qs.filter(program_id=program)
    if academic_year:
        qs = qs.filter(academic_year=academic_year)
    qs = qs.order_by("student_id")
    paginator = Paginator(qs, 15)
    page_obj = paginator.get_page(request.GET.get("page"))

    return render(
        request,
        "students/student_list.html",
        {
            "students": page_obj.object_list,
            "page_obj": page_obj,
            "program_options": Program.objects.filter(is_active=True).order_by("name"),
            "year_options": Student.objects.exclude(academic_year="").values_list("academic_year", flat=True).distinct().order_by("academic_year"),
        },
    )


@login_required
def program_quick_add(request):
    if not _is_admin(request.user):
        return HttpResponseForbidden("Not allowed")
    if request.method == "POST":
        form = QuickProgramForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Program added.")
        else:
            messages.error(request, " ".join(form.errors.get("name", ["Invalid program name."])))
    return redirect("students:list")


@login_required
def student_detail(request, pk):
    student = get_object_or_404(Student.objects.select_related("contact", "program", "emergency_contact", "user"), pk=pk)
    if not _is_admin(request.user) and request.user != student.user:
        return HttpResponseForbidden("Not allowed")
    return render(request, "students/student_detail.html", {"student": student})


@login_required
def my_profile(request):
    if _is_admin(request.user):
        return redirect("dashboard:home")
    student = get_object_or_404(Student.objects.select_related("program"), user=request.user)
    return render(request, "students/student_detail.html", {"student": student})


@login_required
def student_create(request):
    if not _is_admin(request.user):
        return HttpResponseForbidden("Not allowed")
    if request.method == "POST":
        form = StudentForm(request.POST, request.FILES)
        if form.is_valid():
            with transaction.atomic():
                student_id = form.cleaned_data["student_id"]
                first_name = form.cleaned_data["first_name"]
                last_name = form.cleaned_data["last_name"]

                student = form.save(commit=False)
                student.save()
                form.save_contact(student)
            create_audit_log(user=request.user, action="student_create", object_modified=student.student_id)
            messages.success(request, "Student created.")
            return redirect("students:detail", pk=student.pk)
    else:
        form = StudentForm()
    return render(request, "students/student_form.html", {"form": form, "title": "Add Student"})


@login_required
def student_edit(request, pk):
    student = get_object_or_404(Student, pk=pk)
    is_admin = _is_admin(request.user)
    if not is_admin and request.user != student.user:
        return HttpResponseForbidden("Not allowed")

    old_student_id = student.student_id

    form = StudentForm(request.POST or None, request.FILES or None, instance=student)

    if not is_admin:
        locked_fields = [
            "student_id",
            "registration_number",
            "program",
            "academic_year",
            "semester",
            "enrollment_date",
            "status",
        ]
        for field_name in locked_fields:
            if field_name in form.fields:
                form.fields[field_name].disabled = True

    if request.method == "POST" and form.is_valid():
        form.save()
        form.save_contact(student)
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
    return render(request, "students/student_form.html", {"form": form, "title": "Edit Student"})


@login_required
def student_delete(request, pk):
    if not _is_admin(request.user):
        return HttpResponseForbidden("Not allowed")
    student = get_object_or_404(Student, pk=pk)
    if request.method == "POST":
        sid = student.student_id
        student.delete()
        create_audit_log(user=request.user, action="student_delete", object_modified=sid)
        return redirect("students:list")
    return render(request, "students/student_confirm_delete.html", {"student": student})


@login_required
def student_toggle_status(request, pk, target):
    if not _is_admin(request.user):
        return HttpResponseForbidden("Not allowed")
    student = get_object_or_404(Student, pk=pk)
    if target not in {Student.Status.ACTIVE, Student.Status.INACTIVE}:
        return HttpResponseForbidden("Invalid status")
    if target == Student.Status.ACTIVE:
        student.restart_subscription()
    else:
        student.status = target
        student.save(update_fields=["status", "updated_at"])
    create_audit_log(user=request.user, action=f"student_status_{target}", object_modified=student.student_id)
    messages.success(request, f"Student status changed to {target.title()}.")
    return redirect("students:list")