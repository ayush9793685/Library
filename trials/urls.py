from django.urls import path

from . import views

app_name = "trials"

urlpatterns = [
    path("", views.trial_list, name="list"),
    path("add/", views.trial_create, name="create"),
    path("<int:pk>/edit/", views.trial_edit, name="edit"),
    path("<int:pk>/delete/", views.trial_delete, name="delete"),
]
