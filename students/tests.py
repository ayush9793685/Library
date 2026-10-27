from django.test import TestCase

from accounts.models import User
from academics.models import Department, Program
from .models import Student


class StudentModelTest(TestCase):
    def test_create_student(self):
        user = User.objects.create_user(username="s1", password="StrongPass@123", role="student")
        department = Department.objects.create(name="Computer Science", code="CS")
        program = Program.objects.create(department=department, name="BSc", code="BSC")
        student = Student.objects.create(
            user=user,
            student_id="S-1",
            first_name="A",
            last_name="B",
            registration_number="R-1",
            department=department,
            program=program,
            academic_year="2026",
            semester="1",
            enrollment_date="2026-01-01",
        )
        self.assertEqual(student.user.username, "s1")

# Create your tests here.
