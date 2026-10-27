from django.urls import path

from .views import export_students_csv

app_name = "reports"

urlpatterns = [
    path("students/csv/", export_students_csv, name="students_csv"),
]
