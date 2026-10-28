from django.urls import path

from . import views

app_name = "attendance"

urlpatterns = [
    path("", views.index, name="index"),
    path("students/", views.student_daily, name="student_daily"),
    path("staff/", views.staff_daily, name="staff_daily"),
    path("scan/", views.scan_page, name="scan"),
    path("scan/api/", views.scan_api, name="scan_api"),
    path("scan/ping/", views.scan_ping, name="scan_ping"),
    path("holidays/add/", views.holiday_add, name="holiday_add"),
    path("holidays/<int:pk>/delete/", views.holiday_delete, name="holiday_delete"),
    path("reports/students/", views.student_report, name="student_report"),
    path("reports/staff/", views.staff_report, name="staff_report"),
    path("me/", views.my_attendance, name="my"),
]
