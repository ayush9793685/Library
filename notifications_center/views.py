from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import HttpResponseForbidden
from django.shortcuts import redirect, render
from django.utils import timezone

from students.models import Student

from .forms import AnnouncementForm
from .models import Announcement


def _is_admin(user):
    return user.is_authenticated and (user.is_staff or user.role == "admin")


@login_required
def index(request):
    today = timezone.localdate()
    if _is_admin(request.user):
        announcements = Announcement.objects.select_related("department").order_by("-publish_date")
        return render(request, "notifications/index.html", {"announcements": announcements, "is_admin": True})

    student = Student.objects.filter(user=request.user).first()
    base = Announcement.objects.filter(is_active=True, publish_date__lte=today)
    active = (base.filter(expiry_date__isnull=True) | base.filter(expiry_date__gte=today)).distinct()
    if student:
        active = active.filter(
            Q(department__isnull=True) | Q(department=student.department),
            Q(semester__exact="") | Q(semester=student.semester),
        ).distinct()
    return render(request, "notifications/index.html", {"announcements": active.order_by("-publish_date"), "is_admin": False})


@login_required
def announcement_create(request):
    if not _is_admin(request.user):
        return HttpResponseForbidden("Not allowed")
    form = AnnouncementForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Announcement created.")
        return redirect("notifications_center:index")
    return render(request, "notifications/form.html", {"form": form, "title": "Create Announcement"})

# Create your views here.
