from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render

from .forms import ProgramForm
from .models import Program


def _is_admin(user):
    return user.is_authenticated and (user.is_staff or user.role == "admin")


@login_required
def index(request):
    if not _is_admin(request.user):
        return HttpResponseForbidden("Not allowed")
    return render(
        request,
        "academics/index.html",
        {"programs": Program.objects.order_by("name")},
    )


@login_required
def program_create(request):
    if not _is_admin(request.user):
        return HttpResponseForbidden("Not allowed")
    form = ProgramForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Program created.")
        return redirect("academics:index")
    return render(request, "academics/form.html", {"form": form, "title": "Add Program"})


@login_required
def program_edit(request, pk):
    if not _is_admin(request.user):
        return HttpResponseForbidden("Not allowed")
    program = get_object_or_404(Program, pk=pk)
    form = ProgramForm(request.POST or None, instance=program)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Program updated.")
        return redirect("academics:index")
    return render(request, "academics/form.html", {"form": form, "title": "Edit Program"})

# Create your views here.
