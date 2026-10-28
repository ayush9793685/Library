from django.urls import path

from . import views

app_name = "reports"

urlpatterns = [
    path("", views.reports_home, name="home"),
    path("fees/", views.fees_report, name="fees"),
    path("students/csv/", views.export_students_csv, name="students_csv"),
]
