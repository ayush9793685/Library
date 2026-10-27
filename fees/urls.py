from django.urls import path

from . import views

app_name = "fees"

urlpatterns = [
    path("", views.index, name="index"),
    path("structures/add/", views.structure_create, name="structure_create"),
    path("students/search/", views.student_search, name="student_search"),
    path("payments/add/", views.payment_create, name="payment_create"),
]
