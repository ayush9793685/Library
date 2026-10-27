from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.shortcuts import redirect, render

from .forms import DocumentForm
from .models import Document


def _is_admin(user):
    return user.is_authenticated and (user.is_staff or user.role == "admin")


@login_required
def index(request):
    if _is_admin(request.user):
        docs = Document.objects.order_by("-created_at")
    else:
        docs = Document.objects.filter(is_public=True).order_by("-created_at")
    return render(request, "documents/index.html", {"documents": docs, "is_admin": _is_admin(request.user)})


@login_required
def document_create(request):
    if not _is_admin(request.user):
        return HttpResponseForbidden("Not allowed")
    form = DocumentForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Document uploaded.")
        return redirect("documents:index")
    return render(request, "documents/form.html", {"form": form, "title": "Upload Document"})

# Create your views here.
