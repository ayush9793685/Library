import calendar
import csv
from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal

from django import forms
from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from django.http import HttpResponse, HttpResponseForbidden
from django.shortcuts import render
from django.utils import timezone

from academics.models import Program
from fees.models import Payment
from students.models import Student

from .exports import export_querystring, maybe_export

SCREEN_ROW_LIMIT = 500


def _admin(user):
    return user.is_authenticated and (user.is_staff or getattr(user, "role", "") == "admin")


def month_bounds(month_value=None):
    """First and last day of a 'YYYY-MM' month (current month by default)."""
    today = timezone.localdate()
    try:
        year, month = [int(p) for p in (month_value or "").split("-")]
        first = date(year, month, 1)
    except (ValueError, TypeError):
        first = today.replace(day=1)
    return first, first.replace(day=calendar.monthrange(first.year, first.month)[1])


class FeesReportForm(forms.Form):
    VIEWS = [
        ("date", "Date-wise"),
        ("batch", "Batch-wise"),
        ("student", "Student-wise"),
        ("receipts", "All receipts"),
    ]
    view = forms.ChoiceField(label="Report", choices=VIEWS, required=False)
    month = forms.CharField(label="Month", required=False, widget=forms.DateInput(attrs={"type": "month"}))
    date_from = forms.DateField(label="From (range)", required=False, widget=forms.DateInput(attrs={"type": "date"}))
    date_to = forms.DateField(label="To (range)", required=False, widget=forms.DateInput(attrs={"type": "date"}))
    batch = forms.ModelChoiceField(label="Batch", queryset=Program.objects.none(), required=False, empty_label="All batches")
    student = forms.CharField(label="Student ID", required=False, max_length=30)
    mode = forms.ChoiceField(label="Payment mode", required=False, choices=[("", "All modes")] + list(Payment.Mode.choices))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["batch"].queryset = Program.objects.filter(is_active=True).order_by("name")


def _fmt(amount):
    return f"{Decimal(amount or 0):,.2f}"


@login_required
def fees_report(request):
    if not _admin(request.user):
        return HttpResponseForbidden("Not allowed")
    form = FeesReportForm(request.GET or None)
    data = form.cleaned_data if form.is_bound and form.is_valid() else {}
    view = data.get("view") or "date"

    # Default: the current month. A From/To range, when both are filled, takes over.
    if data.get("date_from") and data.get("date_to"):
        start, end = data["date_from"], data["date_to"]
        if end < start:
            start, end = end, start
        period = f"{start:%d %b %Y} to {end:%d %b %Y}"
    else:
        start, end = month_bounds(data.get("month"))
        period = f"{start:%B %Y}"

    payments = Payment.objects.filter(is_cancelled=False, paid_on__range=(start, end)).select_related("student", "student__program")
    if data.get("batch"):
        payments = payments.filter(student__program=data["batch"])
    if data.get("student"):
        payments = payments.filter(student_id_text__iexact=data["student"].strip())
    if data.get("mode"):
        payments = payments.filter(payment_mode=data["mode"])

    subtitle = f"Payments received {period}"
    if data.get("batch"):
        subtitle += f" | Batch: {data['batch'].name}"
    cards = []

    if view == "receipts":
        title = "Fees Report - All Receipts"
        headers = ["Receipt", "Date", "Student ID", "Name", "Batch", "Seat", "Mode", "Reference", "Plan period", "Amount"]
        rows = [
            [p.receipt_number, p.paid_on, p.student_id_text, p.student_name,
             p.student.program.name if p.student and p.student.program else "", p.student.seat_number if p.student else "",
             p.get_payment_mode_display(), p.reference,
             f"{p.period_start:%d %b} - {p.period_end:%d %b %Y}" if p.period_start and p.period_end else "", _fmt(p.amount_paid)]
            for p in payments.order_by("paid_on", "id")
        ]
        total = payments.aggregate(t=Sum("amount_paid"))["t"] or 0
        totals = ["", "", "", "", "", "", "", "", "Total", _fmt(total)]
        cards = [("Receipts", len(rows)), ("Total collected", _fmt(total))]

    elif view == "batch":
        title = "Fees Report - Batch-wise"
        headers = ["Batch", "Timings", "Monthly fee", "Students", "Total monthly fees", "Paid (this period)", "Balance due now"]
        paid_by_batch = defaultdict(Decimal)
        for pay in payments:
            key = pay.student.program_id if pay.student else None
            paid_by_batch[key] += pay.amount_paid
        rows, tot_fees, tot_paid, tot_bal, tot_students = [], Decimal(0), Decimal(0), Decimal(0), 0
        batches = Program.objects.filter(is_active=True).order_by("name")
        if data.get("batch"):
            batches = batches.filter(pk=data["batch"].pk)
        for b in batches:
            members = [s for s in Student.objects.filter(program=b).exclude(status=Student.Status.DEACTIVATED)]
            fees = sum((s.monthly_fee for s in members), Decimal(0))
            balance = sum((s.monthly_fee for s in members if s.payment_status != "Paid"), Decimal(0))
            paid = paid_by_batch.get(b.pk, Decimal(0))
            rows.append([b.name, b.timing_display, _fmt(b.monthly_fee), len(members), _fmt(fees), _fmt(paid), _fmt(balance)])
            tot_fees += fees; tot_paid += paid; tot_bal += balance; tot_students += len(members)
        totals = ["Total", "", "", tot_students, _fmt(tot_fees), _fmt(tot_paid), _fmt(tot_bal)]
        cards = [("Students", tot_students), ("Total monthly fees", _fmt(tot_fees)),
                 ("Paid (this period)", _fmt(tot_paid)), ("Balance due now", _fmt(tot_bal))]

    elif view == "student":
        title = "Fees Report - Student-wise"
        headers = ["Student ID", "Name", "Batch", "Seat", "Monthly fee", "Paid (this period)", "Plan ends", "Fee status", "Balance due now"]
        paid_by_student = defaultdict(Decimal)
        for pay in payments:
            paid_by_student[pay.student_id] += pay.amount_paid
        students = Student.objects.select_related("program").exclude(status=Student.Status.DEACTIVATED).order_by("student_id")
        if data.get("batch"):
            students = students.filter(program=data["batch"])
        if data.get("student"):
            students = students.filter(student_id__iexact=data["student"].strip())
        rows, tot_fee, tot_paid, tot_bal = [], Decimal(0), Decimal(0), Decimal(0)
        for s in students:
            status = s.payment_status
            balance = Decimal(0) if status == "Paid" else s.monthly_fee
            paid = paid_by_student.get(s.pk, Decimal(0))
            name = " ".join(p for p in [s.first_name, s.middle_name, s.last_name] if p)
            rows.append([s.student_id, name, s.program.name if s.program else "", s.seat_number or "",
                         _fmt(s.monthly_fee), _fmt(paid),
                         timezone.localtime(s.subscription_end).date() if s.subscription_end else "", status, _fmt(balance)])
            tot_fee += s.monthly_fee; tot_paid += paid; tot_bal += balance
        totals = ["Total", "", "", "", _fmt(tot_fee), _fmt(tot_paid), "", "", _fmt(tot_bal)]
        cards = [("Students", len(rows)), ("Total monthly fees", _fmt(tot_fee)),
                 ("Paid (this period)", _fmt(tot_paid)), ("Balance due now", _fmt(tot_bal))]

    else:  # date-wise
        title = "Fees Report - Date-wise"
        headers = ["Date", "Receipts", "Cash", "UPI", "Total"]
        per_day = defaultdict(lambda: {"n": 0, "cash": Decimal(0), "upi": Decimal(0)})
        for pay in payments:
            d = per_day[pay.paid_on]
            d["n"] += 1
            d["upi" if pay.payment_mode == Payment.Mode.UPI else "cash"] += pay.amount_paid
        rows, n, cash, upi = [], 0, Decimal(0), Decimal(0)
        for day in sorted(per_day):
            d = per_day[day]
            rows.append([day, d["n"], _fmt(d["cash"]), _fmt(d["upi"]), _fmt(d["cash"] + d["upi"])])
            n += d["n"]; cash += d["cash"]; upi += d["upi"]
        totals = ["Total", n, _fmt(cash), _fmt(upi), _fmt(cash + upi)]
        cards = [("Receipts", n), ("Cash", _fmt(cash)), ("UPI", _fmt(upi)), ("Total collected", _fmt(cash + upi))]

    exported = maybe_export(request, filename="fees_report_" + view, title=title, subtitle=subtitle,
                            headers=headers, rows=rows, totals=totals)
    if exported:
        return exported
    on_screen = rows[:SCREEN_ROW_LIMIT]
    return render(request, "reports/report_page.html", {
        "title": title, "subtitle": subtitle, "form": form, "headers": headers, "rows": on_screen, "totals": totals,
        "summary_cards": cards, "export_qs": export_querystring(request),
        "truncated": SCREEN_ROW_LIMIT if len(rows) > SCREEN_ROW_LIMIT else None,
    })


@login_required
def reports_home(request):
    if not _admin(request.user):
        return HttpResponseForbidden("Not allowed")
    return render(request, "reports/home.html")


@login_required
def export_students_csv(request):
    """Student directory. Aadhaar is masked (last 4 only); the full number is never exported."""
    if not _admin(request.user):
        return HttpResponseForbidden("Not allowed")
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = 'attachment; filename="student_directory.csv"'
    response.write("﻿")  # lets Excel read names correctly
    writer = csv.writer(response)
    writer.writerow([
        "Student ID", "Name", "Registration No", "Batch", "Seat No", "Monthly Fee",
        "Status", "Fee Status", "Plan Valid Until", "Aadhaar (masked)", "RFID Card",
        "Phone", "Alternate Phone", "Email",
    ])
    students = Student.objects.select_related("program", "contact").order_by("student_id")

    def safe(v):
        v = "" if v is None else str(v)
        return "'" + v if v.startswith(("=", "+", "-", "@")) else v

    for s in students.iterator():
        contact = getattr(s, "contact", None)
        name = " ".join(p for p in [s.first_name, s.middle_name, s.last_name] if p)
        writer.writerow([
            s.student_id, safe(name), s.registration_number,
            s.program.name if s.program else "", s.seat_number or "", s.monthly_fee,
            s.get_status_display(), s.payment_status,
            timezone.localtime(s.subscription_end).strftime("%Y-%m-%d") if s.subscription_end else "",
            s.aadhaar_masked, s.rfid_uid or "",
            contact.mobile_number if contact else "",
            contact.alternate_mobile_number if contact else "",
            contact.primary_email if contact else "",
        ])
    return response
