from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from academics.models import Course
from students.models import Student

from .forms import CourseOfferingForm, RegistrationWindowForm
from .models import CourseOffering, CourseRegistration, RegistrationWindow


def _is_admin(user):
    return user.is_authenticated and (user.is_staff or user.role == "admin")


@login_required
def index(request):
    if _is_admin(request.user):
        offerings = CourseOffering.objects.select_related("registration_window", "course", "course__department").all().order_by("course__code")
        windows = RegistrationWindow.objects.order_by("-starts_at")
        pending = CourseRegistration.objects.filter(status=CourseRegistration.Status.PENDING).select_related("offering", "offering__course", "student")
        return render(request, "registration/admin_index.html", {"offerings": offerings, "windows": windows, "pending": pending})

    student = get_object_or_404(Student, user=request.user)
    now = timezone.now()
    offerings = CourseOffering.objects.select_related("registration_window", "course", "course__department").filter(registration_window__is_active=True, registration_window__starts_at__lte=now, registration_window__ends_at__gte=now)
    regs = CourseRegistration.objects.filter(student=student).select_related("offering", "offering__course", "offering__registration_window")
    return render(request, "registration/student_index.html", {"student": student, "offerings": offerings, "registrations": regs})


@login_required
def window_create(request):
    if not _is_admin(request.user):
        return HttpResponseForbidden("Not allowed")
    form = RegistrationWindowForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Registration window created.")
        return redirect("registration:index")
    return render(request, "registration/form.html", {"form": form, "title": "Create Registration Window"})


@login_required
def offering_create(request):
    if not _is_admin(request.user):
        return HttpResponseForbidden("Not allowed")
    form = CourseOfferingForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Course offering created.")
        return redirect("registration:index")
    return render(request, "registration/form.html", {"form": form, "title": "Create Course Offering"})


@login_required
def register_course(request, offering_id):
    student = get_object_or_404(Student, user=request.user)
    offering = get_object_or_404(CourseOffering, pk=offering_id)
    reg, created = CourseRegistration.objects.get_or_create(
        student=student,
        offering=offering,
        defaults={"status": CourseRegistration.Status.PENDING},
    )
    if not created and reg.status == CourseRegistration.Status.DROPPED:
        reg.status = CourseRegistration.Status.PENDING
        reg.save(update_fields=["status"])
    messages.success(request, "Course registration submitted.")
    return redirect("registration:index")


@login_required
def drop_course(request, registration_id):
    student = get_object_or_404(Student, user=request.user)
    reg = get_object_or_404(CourseRegistration, pk=registration_id, student=student)
    reg.status = CourseRegistration.Status.DROPPED
    reg.save(update_fields=["status"])
    messages.success(request, "Course dropped.")
    return redirect("registration:index")


@login_required
def approve_registration(request, registration_id):
    if not _is_admin(request.user):
        return HttpResponseForbidden("Not allowed")
    reg = get_object_or_404(CourseRegistration, pk=registration_id)
    reg.status = CourseRegistration.Status.APPROVED
    reg.save(update_fields=["status"])
    messages.success(request, "Registration approved.")
    return redirect("registration:index")

# Create your views here.