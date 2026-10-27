from django.contrib import admin

from .models import Address, ContactInformation, EmergencyContact, Student


admin.site.register(Student)
admin.site.register(ContactInformation)
admin.site.register(Address)
admin.site.register(EmergencyContact)

# Register your models here.
