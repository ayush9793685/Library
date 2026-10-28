from django.contrib import admin

from .models import Holiday, StaffAttendance, StudentAttendance

admin.site.register(Holiday)
admin.site.register(StudentAttendance)
admin.site.register(StaffAttendance)
