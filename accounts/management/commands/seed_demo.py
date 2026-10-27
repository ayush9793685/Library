from django.core.management.base import BaseCommand

from accounts.models import User
from students.models import ContactInformation, Student


class Command(BaseCommand):
    help = "Create admin and demo student account"

    def handle(self, *args, **options):
        admin, _ = User.objects.get_or_create(
            username="admin",
            defaults={"email": "admin@sims.local", "role": "admin", "is_staff": True, "is_superuser": True},
        )
        admin.set_password("Admin@12345")
        admin.save()

        stu_user, _ = User.objects.get_or_create(
            username="student1", defaults={"email": "student1@sims.local", "role": "student"}
        )
        stu_user.set_password("Student@12345")
        stu_user.save()

        student, _ = Student.objects.get_or_create(
            user=stu_user,
            defaults={
                "student_id": "STU-0001",
                "first_name": "Demo",
                "last_name": "Student",
                "registration_number": "REG-0001",
                "department": "Computer Science",
                "program": "BSc",
                "academic_year": "2026",
                "semester": "1",
                "enrollment_date": "2026-01-01",
            },
        )
        ContactInformation.objects.get_or_create(
            student=student,
            defaults={"primary_email": "student1@sims.local", "mobile_number": "+10000000000"},
        )
        self.stdout.write(self.style.SUCCESS("Demo users created."))
