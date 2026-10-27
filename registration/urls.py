from django.urls import path

from . import views

app_name = "registration"

urlpatterns = [
    path("", views.index, name="index"),
    path("windows/add/", views.window_create, name="window_create"),
    path("offerings/add/", views.offering_create, name="offering_create"),
    path("offerings/<int:offering_id>/register/", views.register_course, name="register_course"),
    path("registrations/<int:registration_id>/drop/", views.drop_course, name="drop_course"),
    path("registrations/<int:registration_id>/approve/", views.approve_registration, name="approve_registration"),
]
