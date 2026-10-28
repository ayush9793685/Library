import tempfile
from datetime import datetime, timedelta

from django.test import TestCase, override_settings
from django.utils import timezone

from accounts.models import User
from students.models import Student
from students.testutils import batch, make_admin, make_student_row

from . import services
from .models import Holiday, StaffAttendance, StudentAttendance


def at(hour, minute=0, day=None):
    day = day or timezone.localdate()
    return timezone.make_aware(datetime.combine(day, datetime.min.time().replace(hour=hour, minute=minute)))


class ScanTests(TestCase):
    def setUp(self):
        self.pratibha, self.sankalp = batch("Pratibha"), batch("Sankalp")
        self.s = make_student_row(self.pratibha, seat=1, rfid_uid="CARD-A")
        self.s.subscription_end = timezone.now() + timedelta(days=10)
        self.s.save()

    def test_first_scan_marks_present_with_check_in(self):
        r = services.process_scan("CARD-A", at(9))
        self.assertTrue(r["ok"])
        rec = StudentAttendance.objects.get(student=self.s)
        self.assertEqual(rec.status, "present")
        self.assertEqual(rec.source, "rfid")
        self.assertFalse(rec.outside_shift)

    def test_double_tap_ignored_then_later_scan_records_exit(self):
        services.process_scan("CARD-A", at(9))
        r = services.process_scan("CARD-A", at(9) + timedelta(seconds=10))
        self.assertEqual(r["level"], "info")
        self.assertIsNone(StudentAttendance.objects.get().check_out)
        services.process_scan("CARD-A", at(13))
        self.assertIsNotNone(StudentAttendance.objects.get().check_out)
        self.assertEqual(StudentAttendance.objects.count(), 1)

    def test_scan_outside_batch_timings_is_accepted_but_flagged(self):
        r = services.process_scan("CARD-A", at(20))  # Pratibha is 7:00-14:00
        self.assertTrue(r["ok"])
        self.assertTrue(StudentAttendance.objects.get().outside_shift)

    def test_unknown_card(self):
        r = services.process_scan("NOPE")
        self.assertFalse(r["ok"])
        self.assertEqual(StudentAttendance.objects.count(), 0)

    def test_expired_plan_card_is_blocked_until_payment(self):
        self.s.status = Student.Status.INACTIVE
        self.s.subscription_end = timezone.now() - timedelta(days=1)
        self.s.save()
        r = services.process_scan("CARD-A", at(9))
        self.assertFalse(r["ok"])
        self.assertIn("expired", r["message"].lower())
        self.assertEqual(StudentAttendance.objects.count(), 0)

    def test_plan_ended_but_status_not_yet_updated_is_blocked(self):
        self.s.subscription_end = at(9) - timedelta(minutes=5)
        self.s.save()
        self.assertFalse(services.process_scan("CARD-A", at(9))["ok"])

    def test_deactivated_card_is_disabled_permanently(self):
        self.s.status = Student.Status.DEACTIVATED
        self.s.save()
        r = services.process_scan("CARD-A", at(9))
        self.assertFalse(r["ok"])
        self.assertIn("disabled", r["message"].lower())

    def test_scan_corrects_earlier_absent(self):
        StudentAttendance.objects.create(student=self.s, date=timezone.localdate(), status="absent", source="auto")
        self.assertTrue(services.process_scan("CARD-A", at(10))["ok"])
        self.assertEqual(StudentAttendance.objects.get().status, "present")


class AbsenteeTests(TestCase):
    def setUp(self):
        self.p = batch("Pratibha")
        self.a = make_student_row(self.p, seat=1)
        self.b = make_student_row(self.p, seat=2)
        self.gone = make_student_row(self.p, status=Student.Status.DEACTIVATED)

    def test_marks_only_unmarked_active_students(self):
        day = timezone.localdate()
        StudentAttendance.objects.create(student=self.a, date=day, status="leave")
        n = services.mark_absentees(day)
        self.assertEqual(n, 1)
        self.assertEqual(StudentAttendance.objects.get(student=self.b, date=day).status, "absent")
        self.assertEqual(StudentAttendance.objects.get(student=self.a, date=day).status, "leave")
        self.assertFalse(StudentAttendance.objects.filter(student=self.gone).exists())
        self.assertEqual(services.mark_absentees(day), 0)  # idempotent

    def test_holiday_marks_nobody(self):
        day = timezone.localdate()
        Holiday.objects.create(date=day, name="Diwali")
        self.assertIsNone(services.mark_absentees(day))
        self.assertEqual(StudentAttendance.objects.count(), 0)


PRIVATE = tempfile.mkdtemp()


@override_settings(PRIVATE_MEDIA_ROOT=PRIVATE)
class ScreensTests(TestCase):
    def setUp(self):
        self.admin = make_admin()
        self.client.force_login(self.admin)
        self.p = batch("Pratibha")
        self.a = make_student_row(self.p, seat=1)
        self.b = make_student_row(self.p, seat=2)
        self.today = timezone.localdate().isoformat()

    def test_pages_render(self):
        for url in ["/attendance/", "/attendance/students/", "/attendance/staff/", "/attendance/scan/",
                    "/attendance/reports/students/", "/attendance/reports/staff/", "/reports/", "/reports/fees/"]:
            self.assertEqual(self.client.get(url).status_code, 200, url)

    def test_mark_student_attendance_present_absent_leave(self):
        r = self.client.post("/attendance/students/", {"date": self.today, "action": "save",
                                                       f"status_{self.a.pk}": "present", f"status_{self.b.pk}": "leave",
                                                       f"remarks_{self.b.pk}": "Family function"})
        self.assertEqual(r.status_code, 302)
        self.assertEqual(StudentAttendance.objects.get(student=self.a).status, "present")
        rec = StudentAttendance.objects.get(student=self.b)
        self.assertEqual((rec.status, rec.remarks, rec.source), ("leave", "Family function", "manual"))
        # re-saving changes, never duplicates
        self.client.post("/attendance/students/", {"date": self.today, "action": "save", f"status_{self.b.pk}": "absent"})
        self.assertEqual(StudentAttendance.objects.filter(student=self.b).count(), 1)
        self.assertEqual(StudentAttendance.objects.get(student=self.b).status, "absent")

    def test_invalid_status_value_is_ignored(self):
        self.client.post("/attendance/students/", {"date": self.today, "action": "save", f"status_{self.a.pk}": "bogus"})
        self.assertEqual(StudentAttendance.objects.count(), 0)

    def test_future_date_rejected(self):
        future = (timezone.localdate() + timedelta(days=3)).isoformat()
        self.client.post("/attendance/students/", {"date": future, "action": "all_present"})
        self.assertEqual(StudentAttendance.objects.count(), 0)

    def test_batch_filter_and_mark_all_present(self):
        other = make_student_row(batch("Sankalp"), seat=3)
        self.client.post("/attendance/students/", {"date": self.today, "batch": self.p.pk, "action": "all_present"})
        self.assertEqual(StudentAttendance.objects.filter(status="present").count(), 2)
        self.assertFalse(StudentAttendance.objects.filter(student=other).exists())

    def test_staff_attendance(self):
        staff = User.objects.create_user(username="desk1", password="StrongPass@123", role="admin")
        r = self.client.post("/attendance/staff/", {"date": self.today, "action": "save", f"status_{staff.pk}": "leave"})
        self.assertEqual(r.status_code, 302)
        self.assertEqual(StaffAttendance.objects.get(user=staff).status, "leave")
        self.client.post("/attendance/staff/", {"date": self.today, "action": "all_present"})
        self.assertEqual(StaffAttendance.objects.get(user=staff).status, "present")
        # one record per staff member per day (the logged-in admin is staff too)
        self.assertEqual(StaffAttendance.objects.filter(user=staff).count(), 1)
        self.assertEqual(StaffAttendance.objects.count(), 2)

    def test_scan_api_flow_and_permissions(self):
        self.a.rfid_uid = "C1"
        self.a.subscription_end = timezone.now() + timedelta(days=5)
        self.a.save()
        r = self.client.post("/attendance/scan/api/", {"card": "C1"})
        self.assertTrue(r.json()["ok"])
        self.client.logout()
        stu = User.objects.create_user(username="stux", password="StrongPass@123", role="student")
        self.client.force_login(stu)
        self.assertEqual(self.client.post("/attendance/scan/api/", {"card": "C1"}).status_code, 403)

    def test_student_sees_only_own_attendance(self):
        owner = User.objects.create_user(username="own", password="StrongPass@123", role="student")
        self.a.user = owner
        self.a.save()
        StudentAttendance.objects.create(student=self.a, date=timezone.localdate(), status="present")
        StudentAttendance.objects.create(student=self.b, date=timezone.localdate(), status="absent")
        self.client.force_login(owner)
        r = self.client.get("/attendance/me/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.context["counts"]["present"], 1)
        self.assertEqual(r.context["counts"]["absent"], 0)
        self.assertEqual(self.client.get("/attendance/students/").status_code, 403)

    def test_holiday_add_and_remove(self):
        self.client.post("/attendance/holidays/add/", {"date": self.today, "name": "Test day"})
        h = Holiday.objects.get()
        self.client.post(f"/attendance/holidays/{h.pk}/delete/")
        self.assertEqual(Holiday.objects.count(), 0)
