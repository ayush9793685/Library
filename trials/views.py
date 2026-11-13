from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .forms import TrialVisitorForm
from .models import TrialVisitor


def _is_admin(user):
    return user.is_authenticated and (user.is_staff or user.role == "admin")


@login_required
def trial_list(request):
    if not _is_admin(request.user):
        return HttpResponseForbidden("Not allowed")
    qs = TrialVisitor.objects.select_related("program", "student")
    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(Q(name__icontains=q) | Q(phone__icontains=q))
    status = request.GET.get("status", "").strip()
    if status in TrialVisitor.Status.values:
        qs = qs.filter(status=status)
    page_obj = Paginator(qs, 20).get_page(request.GET.get("page"))
    return render(request, "trials/list.html", {
        "page_obj": page_obj, "visitors": page_obj.object_list,
        "status_choices": TrialVisitor.Status.choices, "q": q, "status": status,
    })


@login_required
def trial_create(request):
    if not _is_admin(request.user):
        return HttpResponseForbidden("Not allowed")
    form = TrialVisitorForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Trial visitor added.")
        return redirect("trials:list")
    return render(request, "trials/form.html", {"form": form, "title": "Add Trial Visitor"})


@login_required
def trial_edit(request, pk):
    if not _is_admin(request.user):
        return HttpResponseForbidden("Not allowed")
    visitor = get_object_or_404(TrialVisitor, pk=pk)
    form = TrialVisitorForm(request.POST or None, instance=visitor)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Trial visitor updated.")
        return redirect("trials:list")
    return render(request, "trials/form.html", {"form": form, "title": "Edit Trial Visitor"})


@login_required
@require_POST
def trial_delete(request, pk):
    if not _is_admin(request.user):
        return HttpResponseForbidden("Not allowed")
    get_object_or_404(TrialVisitor, pk=pk).delete()
    messages.success(request, "Trial visitor removed.")
    return redirect("trials:list")
