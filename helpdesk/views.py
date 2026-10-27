from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render

from students.models import Student

from .forms import TicketForm, TicketReplyForm
from .models import Ticket, TicketReply


def _is_admin(user):
    return user.is_authenticated and (user.is_staff or user.role == "admin")


@login_required
def index(request):
    if _is_admin(request.user):
        tickets = Ticket.objects.select_related("student").order_by("-created_at")
    else:
        student = get_object_or_404(Student, user=request.user)
        tickets = Ticket.objects.filter(student=student).order_by("-created_at")
    return render(request, "helpdesk/index.html", {"tickets": tickets, "is_admin": _is_admin(request.user)})


@login_required
def ticket_create(request):
    student = get_object_or_404(Student, user=request.user)
    form = TicketForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        ticket = form.save(commit=False)
        ticket.student = student
        ticket.save()
        messages.success(request, "Ticket created.")
        return redirect("helpdesk:index")
    return render(request, "helpdesk/form.html", {"form": form, "title": "Create Ticket"})


@login_required
def ticket_detail(request, pk):
    ticket = get_object_or_404(Ticket, pk=pk)
    if not _is_admin(request.user):
        student = get_object_or_404(Student, user=request.user)
        if ticket.student_id != student.student_id and ticket.student != student:
            return HttpResponseForbidden("Not allowed")

    reply_form = TicketReplyForm(request.POST or None)
    if request.method == "POST" and reply_form.is_valid():
        reply = reply_form.save(commit=False)
        reply.ticket = ticket
        reply.author = request.user
        reply.save()
        messages.success(request, "Reply added.")
        return redirect("helpdesk:detail", pk=ticket.pk)

    return render(request, "helpdesk/detail.html", {"ticket": ticket, "reply_form": reply_form})


@login_required
def ticket_set_status(request, pk, status):
    if not _is_admin(request.user):
        return HttpResponseForbidden("Not allowed")
    ticket = get_object_or_404(Ticket, pk=pk)
    valid = {choice[0] for choice in Ticket.Status.choices}
    if status not in valid:
        return HttpResponseForbidden("Invalid status")
    ticket.status = status
    ticket.save(update_fields=["status"])
    messages.success(request, f"Ticket status changed to {status}.")
    return redirect("helpdesk:detail", pk=ticket.pk)

# Create your views here.
