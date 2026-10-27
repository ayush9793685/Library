from django.contrib import admin

from .models import AttendanceRecord, AttendanceSession, Enrollment


@admin.register(Enrollment)
class EnrollmentAdmin(admin.ModelAdmin):
    list_display = ("student_id", "course", "enrolled_at")
    list_filter = ("course",)
    search_fields = ("student_id", "course__code")


@admin.register(AttendanceSession)
class AttendanceSessionAdmin(admin.ModelAdmin):
    list_display = ("session_date", "course", "department", "program", "semester", "time_slot")
    list_filter = ("department", "program", "semester", "time_slot")
    search_fields = ("course__code", "instructor__full_name", "instructor_name")


@admin.register(AttendanceRecord)
class AttendanceRecordAdmin(admin.ModelAdmin):
    list_display = ("student_id", "session", "status", "remarks")
    list_filter = ("status", "session__course")
    search_fields = ("student_id",)
