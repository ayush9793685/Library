from collections import defaultdict
from datetime import datetime

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from audits.utils import create_audit_log
from reports.exports import export_querystring, maybe_export
from reports.views import month_bounds
from students.models import Student

from . import services
from .forms import AttendanceReportForm, DayFilterForm
from .models import Holiday, StaffAttendance, Status, StudentAttendance

SCREEN_ROW_LIMIT = 500
VALID = {s.value for s in Status}


def _is_admin(user):
    return user.is_authenticated and (user.is_staff or getattr(user, "role", "") == "admin")


def _full_name(s):
    return " ".join(p for p in [s.first_name, s.middle_name, s.last_name] if p)


def _time(dt):
    return timezone.localtime(dt).strftime("%I:%M %p").lstrip("0") if dt else ""


@login_required
def index(request):
    if not _is_admin(request.user):
        return redirect("attendance:my")
    today = timezone.localdate()
    counts = {s: StudentAttendance.objects.filter(date=today, status=s).count() for s in VALID}
    staff_counts = {s: StaffAttendance.objects.filter(date=today, status=s).count() for s in VALID}
    return render(request, "attendance/index.html", {
        "today": today, "counts": counts, "staff_counts": staff_counts,
        "active_students": Student.objects.filter(status=Student.Status.ACTIVE).count(),
        "holiday": Holiday.objects.filter(date=today).first(),
        "holidays": Holiday.objects.filter(date__gte=today).order_by("date")[:5],
    })


# ----------------------------------------------------------------- RFID scan
@login_required
def scan_page(request):
    if not _is_admin(request.user):
        return HttpResponseForbidden("Not allowed")
    recent = StudentAttendance.objects.filter(source=StudentAttendance.Source.RFID, date=timezone.localdate()) \
        .select_related("student").order_by("-updated_at")[:10]
    return render(request, "attendance/scan.html", {"recent": recent})


@login_required
@require_POST
def scan_api(request):
    if not _is_admin(request.user):
        return JsonResponse({"ok": False, "level": "error", "message": "Not allowed."}, status=403)
    result = services.process_scan(request.POST.get("card", ""))
    return JsonResponse(result)


@login_required
def scan_ping(request):
    """Keeps the scan station's login alive (sessions otherwise expire after 30 idle minutes)."""
    return JsonResponse({"ok": _is_admin(request.user)})


# ------------------------------------------------------ daily marking screens
def _save_marks(request, model, key_field, ids, day, label):
    changed = 0
    for pk in ids:
        value = request.POST.get(f"status_{pk}", "")
        remark = request.POST.get(f"remarks_{pk}", "").strip()[:255]
        if value not in VALID:
            continue
        defaults = {"status": value, "remarks": remark, "marked_by": request.user}
        if model is StudentAttendance:
            defaults["source"] = StudentAttendance.Source.MANUAL
        obj, created = model.objects.get_or_create(**{key_field: pk, "date": day}, defaults=defaults)
        if not created and (obj.status != value or obj.remarks != remark):
            for k, v in defaults.items():
                setattr(obj, k, v)
            obj.save()  # scan in/out times stay as history
            changed += 1
        elif created:
            changed += 1
    create_audit_log(user=request.user, action=f"{label}_attendance_marked", object_modified=str(day), new_value=f"{changed} record(s)")
    return changed


@login_required
def student_daily(request):
    if not _is_admin(request.user):
        return HttpResponseForbidden("Not allowed")
    form = DayFilterForm(request.GET or request.POST or None)
    day, batch = timezone.localdate(), None
    if form.is_bound and form.is_valid():
        day, batch = form.cleaned_data["date"], form.cleaned_data.get("batch")
    elif form.is_bound:
        messages.error(request, "; ".join(e for errs in form.errors.values() for e in errs))
    students = Student.objects.select_related("program").exclude(status=Student.Status.DEACTIVATED).order_by("student_id")
    if batch:
        students = students.filter(program=batch)
    students = list(students)

    if request.method == "POST" and form.is_valid():
        action = request.POST.get("action", "save")
        with transaction.atomic():
            if action == "all_present":
                for s in students:
                    StudentAttendance.objects.update_or_create(
                        student=s, date=day,
                        defaults={"status": Status.PRESENT, "marked_by": request.user, "source": StudentAttendance.Source.MANUAL},
                    )
                messages.success(request, f"{len(students)} student(s) marked Present for {day:%d %b %Y}.")
            elif action == "absentees":
                count = services.mark_absentees(day, batch)
                if count is None:
                    messages.info(request, f"{day:%d %b %Y} is a holiday, so nobody was marked Absent.")
                else:
                    messages.success(request, f"{count} student(s) with no record were marked Absent.")
            else:
                changed = _save_marks(request, StudentAttendance, "student_id", [s.pk for s in students], day, "student")
                messages.success(request, f"Attendance saved ({changed} change(s)).")
        return redirect(f"{request.path}?date={day.isoformat()}" + (f"&batch={batch.pk}" if batch else ""))

    records = {r.student_id: r for r in StudentAttendance.objects.filter(date=day, student__in=students)}
    rows = []
    for s in students:
        r = records.get(s.pk)
        rows.append({
            "id": s.pk, "label": f"{s.student_id} - {_full_name(s)}",
            "sub": f"{s.program.name if s.program else '-'} · Seat {s.seat_number or '-'}"
                   + (" · Plan expired" if s.status == Student.Status.INACTIVE else ""),
            "status": r.status if r else "", "remarks": r.remarks if r else "",
            "times": (f"In {_time(r.check_in)}" + (f" / Out {_time(r.check_out)}" if r.check_out else "")) if r and r.check_in else "",
            "flag": "outside shift" if r and r.outside_shift else "",
        })
    return render(request, "attendance/mark_daily.html", {
        "title": "Student Attendance", "form": form, "rows": rows, "day": day, "is_student": True,
        "holiday": Holiday.objects.filter(date=day).first(), "report_url": "attendance:student_report",
    })


@login_required
def staff_daily(request):
    if not _is_admin(request.user):
        return HttpResponseForbidden("Not allowed")
    form = DayFilterForm(request.GET or request.POST or None, show_batch=False)
    day = timezone.localdate()
    if form.is_bound and form.is_valid():
        day = form.cleaned_data["date"]
    elif form.is_bound:
        messages.error(request, "; ".join(e for errs in form.errors.values() for e in errs))
    staff = list(services.staff_queryset())

    if request.method == "POST" and form.is_valid():
        action = request.POST.get("action", "save")
        with transaction.atomic():
            if action == "all_present":
                for u in staff:
                    StaffAttendance.objects.update_or_create(user=u, date=day, defaults={"status": Status.PRESENT, "marked_by": request.user})
                messages.success(request, f"{len(staff)} staff member(s) marked Present for {day:%d %b %Y}.")
            else:
                changed = _save_marks(request, StaffAttendance, "user_id", [u.pk for u in staff], day, "staff")
                messages.success(request, f"Staff attendance saved ({changed} change(s)).")
        return redirect(f"{request.path}?date={day.isoformat()}")

    records = {r.user_id: r for r in StaffAttendance.objects.filter(date=day, user__in=staff)}
    rows = []
    for u in staff:
        r = records.get(u.pk)
        rows.append({"id": u.pk, "label": u.get_full_name() or u.username, "sub": u.username,
                     "status": r.status if r else "", "remarks": r.remarks if r else "", "times": "", "flag": ""})
    return render(request, "attendance/mark_daily.html", {
        "title": "Staff Attendance", "form": form, "rows": rows, "day": day, "is_student": False,
        "holiday": Holiday.objects.filter(date=day).first(), "report_url": "attendance:staff_report",
    })


@login_required
@require_POST
def holiday_add(request):
    if not _is_admin(request.user):
        return HttpResponseForbidden("Not allowed")
    name = request.POST.get("name", "").strip()[:120]
    try:
        day = datetime.strptime(request.POST.get("date", ""), "%Y-%m-%d").date()
    except ValueError:
        messages.error(request, "Enter a valid holiday date.")
        return redirect("attendance:index")
    if not name:
        messages.error(request, "Give the holiday a name.")
    else:
        Holiday.objects.get_or_create(date=day, defaults={"name": name})
        messages.success(request, f"Holiday added: {name} ({day:%d %b %Y}).")
    return redirect("attendance:index")


@login_required
@require_POST
def holiday_delete(request, pk):
    if not _is_admin(request.user):
        return HttpResponseForbidden("Not allowed")
    get_object_or_404(Holiday, pk=pk).delete()
    messages.success(request, "Holiday removed.")
    return redirect("attendance:index")


# ------------------------------------------------------------------- reports
def _range_from(data):
    if data.get("date_from") and data.get("date_to"):
        start, end = data["date_from"], data["date_to"]
        if end < start:
            start, end = end, start
        return start, end, f"{start:%d %b %Y} to {end:%d %b %Y}"
    start, end = month_bounds(data.get("month"))
    return start, end, f"{start:%B %Y}"


def _pct(present, total):
    return f"{(present / total * 100):.1f}%" if total else "-"


@login_required
def student_report(request):
    if not _is_admin(request.user):
        return HttpResponseForbidden("Not allowed")
    form = AttendanceReportForm(request.GET or None)
    data = form.cleaned_data if form.is_bound and form.is_valid() else {}
    view = data.get("view") or "records"
    start, end, period = _range_from(data)
    qs = StudentAttendance.objects.filter(date__range=(start, end)).select_related("student", "student__program")
    if data.get("batch"):
        qs = qs.filter(student__program=data["batch"])
    if data.get("who"):
        qs = qs.filter(student__student_id__iexact=data["who"].strip())
    if data.get("status"):
        qs = qs.filter(status=data["status"])
    subtitle = f"{period}" + (f" | Batch: {data['batch'].name}" if data.get("batch") else "")
    totals, cards = None, []

    if view == "summary":
        title = "Student Attendance - Summary"
        headers = ["Student ID", "Name", "Batch", "Seat", "Present", "Absent", "Leave", "Days marked", "Attendance %"]
        agg = defaultdict(lambda: {"present": 0, "absent": 0, "leave": 0})
        students = {}
        for r in qs:
            agg[r.student_id][r.status] += 1
            students[r.student_id] = r.student
        rows = []
        tp = ta = tl = 0
        for sid in sorted(agg, key=lambda i: students[i].student_id):
            s, a = students[sid], agg[sid]
            total = a["present"] + a["absent"] + a["leave"]
            rows.append([s.student_id, _full_name(s), s.program.name if s.program else "", s.seat_number or "",
                         a["present"], a["absent"], a["leave"], total, _pct(a["present"], total - a["leave"])])
            tp += a["present"]; ta += a["absent"]; tl += a["leave"]
        totals = ["Total", "", "", "", tp, ta, tl, tp + ta + tl, _pct(tp, tp + ta)]
        cards = [("Students", len(rows)), ("Present", tp), ("Absent", ta), ("Leave", tl)]
    else:
        title = "Student Attendance - Daily Records"
        headers = ["Date", "Student ID", "Name", "Batch", "Seat", "Status", "In", "Out", "Source", "Note"]
        rows = [
            [r.date, r.student.student_id, _full_name(r.student), r.student.program.name if r.student.program else "",
             r.student.seat_number or "", r.get_status_display(), _time(r.check_in), _time(r.check_out),
             r.get_source_display(), "Outside shift" if r.outside_shift else r.remarks]
            for r in qs.order_by("date", "student__student_id")
        ]
        counts = {s: sum(1 for r in rows if r[5] == lbl) for s, lbl in [("p", "Present"), ("a", "Absent"), ("l", "Leave")]}
        cards = [("Records", len(rows)), ("Present", counts["p"]), ("Absent", counts["a"]), ("Leave", counts["l"])]

    exported = maybe_export(request, filename="student_attendance_" + view, title=title, subtitle=subtitle,
                            headers=headers, rows=rows, totals=totals)
    if exported:
        return exported
    return render(request, "reports/report_page.html", {
        "title": title, "subtitle": subtitle, "form": form, "headers": headers, "rows": rows[:SCREEN_ROW_LIMIT],
        "totals": totals, "summary_cards": cards, "export_qs": export_querystring(request),
        "truncated": SCREEN_ROW_LIMIT if len(rows) > SCREEN_ROW_LIMIT else None,
    })


@login_required
def staff_report(request):
    if not _is_admin(request.user):
        return HttpResponseForbidden("Not allowed")
    form = AttendanceReportForm(request.GET or None, staff=True)
    data = form.cleaned_data if form.is_bound and form.is_valid() else {}
    view = data.get("view") or "records"
    start, end, period = _range_from(data)
    qs = StaffAttendance.objects.filter(date__range=(start, end)).select_related("user")
    if data.get("who"):
        qs = qs.filter(user__username__iexact=data["who"].strip())
    if data.get("status"):
        qs = qs.filter(status=data["status"])
    subtitle = period
    totals, cards = None, []

    def name(u):
        return u.get_full_name() or u.username

    if view == "summary":
        title = "Staff Attendance - Summary"
        headers = ["Staff", "Username", "Present", "Absent", "Leave", "Days marked", "Attendance %"]
        agg = defaultdict(lambda: {"present": 0, "absent": 0, "leave": 0})
        users = {}
        for r in qs:
            agg[r.user_id][r.status] += 1
            users[r.user_id] = r.user
        rows = []
        tp = ta = tl = 0
        for uid in sorted(agg, key=lambda i: users[i].username):
            u, a = users[uid], agg[uid]
            total = a["present"] + a["absent"] + a["leave"]
            rows.append([name(u), u.username, a["present"], a["absent"], a["leave"], total, _pct(a["present"], total - a["leave"])])
            tp += a["present"]; ta += a["absent"]; tl += a["leave"]
        totals = ["Total", "", tp, ta, tl, tp + ta + tl, _pct(tp, tp + ta)]
        cards = [("Staff", len(rows)), ("Present", tp), ("Absent", ta), ("Leave", tl)]
    else:
        title = "Staff Attendance - Daily Records"
        headers = ["Date", "Staff", "Username", "Status", "Remarks"]
        rows = [[r.date, name(r.user), r.user.username, r.get_status_display(), r.remarks]
                for r in qs.order_by("date", "user__username")]
        cards = [("Records", len(rows))] + [(lbl, sum(1 for r in rows if r[3] == lbl)) for lbl in ("Present", "Absent", "Leave")]

    exported = maybe_export(request, filename="staff_attendance_" + view, title=title, subtitle=subtitle,
                            headers=headers, rows=rows, totals=totals)
    if exported:
        return exported
    return render(request, "reports/report_page.html", {
        "title": title, "subtitle": subtitle, "form": form, "headers": headers, "rows": rows[:SCREEN_ROW_LIMIT],
        "totals": totals, "summary_cards": cards, "export_qs": export_querystring(request),
        "truncated": SCREEN_ROW_LIMIT if len(rows) > SCREEN_ROW_LIMIT else None,
    })


@login_required
def my_attendance(request):
    student = get_object_or_404(Student, user=request.user)
    start, end = month_bounds(request.GET.get("month"))
    records = StudentAttendance.objects.filter(student=student, date__range=(start, end)).order_by("-date")
    counts = {s: records.filter(status=s).count() for s in VALID}
    total = counts["present"] + counts["absent"]
    return render(request, "attendance/student_view.html", {
        "student": student, "records": records, "counts": counts,
        "percent": _pct(counts["present"], total), "month": start,
    })
