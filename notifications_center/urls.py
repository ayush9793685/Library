from django.urls import path

from . import views

app_name = "notifications_center"

urlpatterns = [
    path("", views.index, name="index"),
    path("add/", views.announcement_create, name="create"),
]
