from django.urls import path

from . import views

app_name = "academics"

urlpatterns = [
    path("", views.index, name="index"),
    path("programs/add/", views.program_create, name="program_create"),
    path("programs/<int:pk>/edit/", views.program_edit, name="program_edit"),
]
