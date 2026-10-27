from django.urls import path

from .views import audit_list

app_name = "audits"

urlpatterns = [path("", audit_list, name="list")]
