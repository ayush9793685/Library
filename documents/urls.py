from django.urls import path

from . import views

app_name = "documents"

urlpatterns = [
    path("", views.index, name="index"),
    path("add/", views.document_create, name="create"),
]
