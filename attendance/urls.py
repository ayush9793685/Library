from django.urls import path

from . import views

app_name = "attendance"

urlpatterns = [
    path("", views.index, name="index"),
    path("sessions/", views.session_list, name="session_list"),
    path("sessions/add/", views.session_create, name="session_create"),
    path("sessions/<int:pk>/mark/", views.mark_attendance, name="mark"),
    path("sessions/<int:pk>/mark-all-present/", views.mark_all_present, name="mark_all_present"),
    path("sessions/<int:pk>/delete/", views.session_delete, name="session_delete"),
    path("export/csv/", views.export_attendance_csv, name="export_csv"),
    path("export/excel/", views.export_attendance_excel, name="export_excel"),
    path("export/pdf/", views.attendance_pdf_view, name="export_pdf"),
]
