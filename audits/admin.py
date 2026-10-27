from django.contrib import admin

from .models import AuditLog


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ("timestamp", "user", "action", "object_modified", "ip_address")
    list_filter = ("action", "timestamp")
    search_fields = ("action", "object_modified", "user__username")

# Register your models here.
