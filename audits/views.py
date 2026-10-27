from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.shortcuts import render

from .models import AuditLog


@login_required
def audit_list(request):
    if not (request.user.is_staff or request.user.role == "admin"):
        return HttpResponseForbidden("Not allowed")
    logs = AuditLog.objects.select_related("user").all()[:300]
    return render(request, "audits/audit_list.html", {"logs": logs})

# Create your views here.
