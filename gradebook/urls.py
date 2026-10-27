from django.urls import path

from . import views

app_name = "gradebook"

urlpatterns = [
    path("", views.index, name="index"),
    path("exams/add/", views.exam_create, name="exam_create"),
    path("exams/<int:pk>/edit/", views.exam_edit, name="exam_edit"),
    path("exams/<int:pk>/publish/", views.publish_exam, name="publish_exam"),
    path("exams/<int:pk>/grades/", views.grade_entry, name="grade_entry"),
    path("my-results/", views.my_results, name="my_results"),
    path("export/csv/", views.export_gradebook_csv, name="export_csv"),
    path("export/excel/", views.export_gradebook_excel, name="export_excel"),
    path("transcript/pdf/", views.transcript_pdf_view, name="transcript_pdf"),
]
