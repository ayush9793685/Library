from django.urls import path

from . import views

app_name = "students"

urlpatterns = [
    path("", views.student_list, name="list"),
    path("me/", views.my_profile, name="my_profile"),
    path("programs/add/", views.program_quick_add, name="program_quick_add"),
    path("add/", views.student_create, name="create"),
    path("<int:pk>/", views.student_detail, name="detail"),
    path("<int:pk>/edit/", views.student_edit, name="edit"),
    path("<int:pk>/delete/", views.student_delete, name="delete"),
    path("<int:pk>/status/<str:target>/", views.student_toggle_status, name="toggle_status"),
]
