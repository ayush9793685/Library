from django.urls import path

from . import views

app_name = "helpdesk"

urlpatterns = [
    path("", views.index, name="index"),
    path("tickets/add/", views.ticket_create, name="create"),
    path("tickets/<int:pk>/", views.ticket_detail, name="detail"),
    path("tickets/<int:pk>/status/<str:status>/", views.ticket_set_status, name="set_status"),
]
