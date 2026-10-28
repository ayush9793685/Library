"""Helpers shared by the test-suites of students, fees, attendance and reports."""
import itertools

from django.core.files.uploadedfile import SimpleUploadedFile

from accounts.models import User
from academics.models import Program
from students.models import ContactInformation, Student
from students.security import _D, _P

_INV = [0, 4, 3, 2, 1, 5, 6, 7, 8, 9]
_counter = itertools.count(1)


def make_aadhaar(prefix="23456789012"):
    """A 12-digit number whose last digit is the correct Verhoeff check digit."""
    c = 0
    for i, ch in enumerate(reversed(prefix)):
        c = _D[c][_P[(i + 1) % 8][int(ch)]]
    return prefix + str(_INV[c])


def unique_aadhaar():
    n = next(_counter)
    return make_aadhaar(f"2{n:010d}")


def make_admin(username="admin1"):
    return User.objects.create_user(username=username, password="StrongPass@123", role="admin")


def batch(name):
    return Program.objects.get(name=name)


def pdf_file(name="aadhaar.pdf"):
    return SimpleUploadedFile(name, b"%PDF-1.4 test aadhaar copy", content_type="application/pdf")


def student_post_data(program, **extra):
    n = next(_counter)
    data = {
        "first_name": "Asha", "middle_name": "", "last_name": f"Test{n}", "gender": "female",
        "mobile_number": "9876543210", "primary_email": f"asha{n}@example.com", "alternate_mobile_number": "",
        "program": program.pk, "monthly_fee": str(program.monthly_fee), "seat_number": "",
        "rfid_uid": "", "aadhaar_number": unique_aadhaar(), "aadhaar_copy": pdf_file(),
        "collect_fee": "on", "payment_mode": "cash", "payment_reference": "",
    }
    data.update(extra)
    return data


def create_student(client, program, **extra):
    """Register a student through the real form; returns the Student."""
    response = client.post("/students/add/", student_post_data(program, **extra))
    assert response.status_code == 302, getattr(response, "context", None) and response.context["form"].errors
    return Student.objects.order_by("-pk").first()


def make_student_row(program, seat=None, status=Student.Status.ACTIVE, **extra):
    """Fast direct creation (no form) for tests that only need rows."""
    n = next(_counter)
    s = Student.objects.create(
        student_id=f"T{n:04d}", registration_number=f"R{n:04d}", first_name="S", last_name=str(n),
        program=program, department=program.department, status=status,
        seat_number=seat, seat_shift=program.shift, **extra,
    )
    ContactInformation.objects.create(student=s, primary_email=f"s{n}@x.com", mobile_number="9999999999")
    return s
