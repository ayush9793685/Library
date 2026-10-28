from django.urls import path

from . import views

app_name = "fees"

urlpatterns = [
    path("", views.index, name="index"),
    path("students/search/", views.student_search, name="student_search"),
    path("payments/add/", views.payment_create, name="payment_create"),
    path("receipt/<int:pk>/", views.receipt, name="receipt"),
    path("receipt/<int:pk>/cancel/", views.payment_cancel, name="payment_cancel"),
    path("receipt/<int:pk>/delete/", views.payment_delete, name="payment_delete"),
]
