import tempfile
from datetime import timedelta
from decimal import Decimal

from django.test import TestCase, override_settings
from django.utils import timezone

from accounts.models import User
from academics.models import Department, Program

from . import seats
from .models import Student
from .security import decrypt_aadhaar, hash_aadhaar, validate_aadhaar, verhoeff_valid
from .testutils import (batch, create_student, make_admin, make_aadhaar, make_student_row, pdf_file,
                        student_post_data, unique_aadhaar)

PRIVATE = tempfile.mkdtemp()


class StudentModelTest(TestCase):
    def test_create_student(self):
        user = User.objects.create_user(username="s1", password="StrongPass@123", role="student")
        department = Department.objects.create(name="Computer Science", code="CS")
        program = Program.objects.create(department=department, name="BSc", code="BSC")
        student = Student.objects.create(
            user=user, student_id="S-1", first_name="A", last_name="B", registration_number="R-1",
            department=department, program=program, academic_year="2026", semester="1", enrollment_date="2026-01-01",
        )
        self.assertEqual(student.user.username, "s1")


class BatchSeedTest(TestCase):
    def test_three_batches_with_required_fees_and_timings(self):
        expected = {"Pratibha": (500, "morning", "07:00", "14:00"),
                    "Pragati": (600, "afternoon", "14:30", "22:00"),
                    "Sankalp": (1000, "full_day", "07:00", "22:00")}
        for name, (fee, shift, start, end) in expected.items():
            b = Program.objects.get(name=name)
            self.assertEqual(b.monthly_fee, Decimal(fee))
            self.assertEqual(b.shift, shift)
            self.assertEqual(b.start_time.strftime("%H:%M"), start)
            self.assertEqual(b.end_time.strftime("%H:%M"), end)


class SeatEngineTest(TestCase):
    def setUp(self):
        self.pratibha, self.pragati, self.sankalp = batch("Pratibha"), batch("Pragati"), batch("Sankalp")

    def test_total_is_80_and_no_reserve(self):
        self.assertEqual(seats.total_seats(), 80)
        self.assertEqual(len(seats.free_seats("full_day")), 80)

    def test_sankalp_needs_a_seat_alone(self):
        make_student_row(self.sankalp, seat=1)
        self.assertFalse(seats.seat_is_free(1, "morning"))
        self.assertFalse(seats.seat_is_free(1, "afternoon"))
        self.assertFalse(seats.seat_is_free(1, "full_day"))

    def test_morning_and_afternoon_share_but_same_shift_does_not(self):
        make_student_row(self.pratibha, seat=5)
        self.assertTrue(seats.seat_is_free(5, "afternoon"))
        self.assertFalse(seats.seat_is_free(5, "morning"))
        self.assertFalse(seats.seat_is_free(5, "full_day"))
        make_student_row(self.pragati, seat=5)
        self.assertFalse(seats.seat_is_free(5, "afternoon"))

    def test_pairing_keeps_empty_seats_for_full_day(self):
        make_student_row(self.pratibha, seat=1)
        self.assertEqual(seats.pick_seat("afternoon"), 1)   # joins the morning student
        self.assertEqual(seats.pick_seat("full_day"), 2)    # never the half-used seat

    def test_deactivated_student_frees_seat(self):
        s = make_student_row(self.sankalp, seat=3)
        self.assertFalse(seats.seat_is_free(3, "full_day"))
        s.status = Student.Status.DEACTIVATED
        s.save()
        self.assertTrue(seats.seat_is_free(3, "full_day"))

    def test_library_full_for_full_day_but_not_for_pairs(self):
        for n in range(1, 81):
            make_student_row(self.pratibha, seat=n)
        self.assertIsNone(seats.pick_seat("morning"))
        self.assertIsNone(seats.pick_seat("full_day"))
        self.assertEqual(seats.pick_seat("afternoon"), 1)

    def test_database_blocks_double_booking_same_shift(self):
        from django.db import IntegrityError, transaction

        make_student_row(self.pratibha, seat=9)
        with self.assertRaises(IntegrityError), transaction.atomic():
            make_student_row(self.pratibha, seat=9)


class PlanAndFeeTest(TestCase):
    def setUp(self):
        self.sankalp = batch("Sankalp")

    def test_new_student_gets_30_day_plan(self):
        s = make_student_row(self.sankalp)
        s.subscription_end = Student._new_end()
        expected = timezone.localdate() + timedelta(days=30)
        self.assertEqual(timezone.localtime(s.subscription_end).date(), expected)

    def test_batch_fee_and_custom_fee(self):
        s = make_student_row(self.sankalp)
        self.assertEqual(s.monthly_fee, Decimal("1000"))
        self.assertFalse(s.has_custom_fee)
        s.custom_monthly_fee = Decimal("750")
        self.assertEqual(s.monthly_fee, Decimal("750"))
        self.assertTrue(s.has_custom_fee)

    def test_batch_fee_change_applies_to_existing_students(self):
        s = make_student_row(self.sankalp)
        self.sankalp.monthly_fee = Decimal("1200")
        self.sankalp.save()
        s.refresh_from_db()
        self.assertEqual(s.monthly_fee, Decimal("1200"))

    def test_renewal_on_time_starts_from_old_end_date(self):
        s = make_student_row(self.sankalp)
        old_end_date = timezone.localdate() + timedelta(days=5)
        s.subscription_end = Student._new_end(old_end_date - timedelta(days=30))
        s.save()
        s.renew_subscription()
        s.refresh_from_db()
        self.assertEqual(timezone.localtime(s.subscription_end).date(), old_end_date + timedelta(days=30))

    def test_renewal_late_starts_from_payment_day(self):
        s = make_student_row(self.sankalp, status=Student.Status.INACTIVE)
        s.subscription_end = timezone.now() - timedelta(days=10)
        s.save()
        s.renew_subscription()
        s.refresh_from_db()
        self.assertEqual(timezone.localtime(s.subscription_end).date(), timezone.localdate() + timedelta(days=30))
        self.assertEqual(s.status, Student.Status.ACTIVE)

    def test_expiry_makes_inactive_not_deactivated(self):
        s = make_student_row(self.sankalp)
        s.subscription_end = timezone.now() - timedelta(minutes=1)
        s.save()
        Student.expire_overdue()
        s.refresh_from_db()
        self.assertEqual(s.status, Student.Status.INACTIVE)

    def test_deactivated_is_never_renewed_or_expired_back(self):
        s = make_student_row(self.sankalp, status=Student.Status.DEACTIVATED)
        self.assertIsNone(s.renew_subscription())
        s.refresh_from_db()
        self.assertEqual(s.status, Student.Status.DEACTIVATED)


class AadhaarSecurityTest(TestCase):
    def test_verhoeff_and_validation(self):
        good = make_aadhaar()
        self.assertTrue(verhoeff_valid(good))
        self.assertEqual(validate_aadhaar(good[:4] + " " + good[4:8] + " " + good[8:]), good)
        bad = good[:-1] + str((int(good[-1]) + 1) % 10)
        with self.assertRaises(Exception):
            validate_aadhaar(bad)
        for wrong in ["12345", "abcdefghijkl", "023456789012", "123456789012"]:
            with self.assertRaises(Exception):
                validate_aadhaar(wrong)

    def test_encryption_roundtrip_hash_and_mask(self):
        s = make_student_row(batch("Pratibha"))
        number = unique_aadhaar()
        s.set_aadhaar(number)
        s.save()
        s.refresh_from_db()
        self.assertNotIn(number, s.aadhaar_encrypted)
        self.assertNotIn(number[:8], s.aadhaar_encrypted)
        self.assertEqual(decrypt_aadhaar(s.aadhaar_encrypted), number)
        self.assertEqual(s.aadhaar_hash, hash_aadhaar(number))
        self.assertEqual(s.aadhaar_masked, f"XXXX XXXX {number[-4:]}")


@override_settings(PRIVATE_MEDIA_ROOT=PRIVATE, SESSION_COOKIE_AGE=1800)
class RegistrationFlowTest(TestCase):
    def setUp(self):
        self.admin = make_admin()
        self.client.force_login(self.admin)
        self.pratibha, self.pragati, self.sankalp = batch("Pratibha"), batch("Pragati"), batch("Sankalp")

    def test_register_assigns_seat_fee_plan_and_receipt(self):
        s = create_student(self.client, self.sankalp)
        self.assertEqual(s.seat_number, 1)
        self.assertEqual(s.monthly_fee, Decimal("1000"))
        self.assertEqual(s.payments.count(), 1)
        p = s.payments.get()
        self.assertEqual(p.amount_paid, Decimal("1000"))
        self.assertFalse(p.extends_plan)
        # registration payment does not double the 30 days
        self.assertEqual(timezone.localtime(s.subscription_end).date(), timezone.localdate() + timedelta(days=30))
        self.assertTrue(s.aadhaar_copy.name.startswith("aadhaar/"))
        self.assertEqual(s.payment_status, "Paid")

    def test_seats_are_automatic_unique_and_shared_by_timing(self):
        a = create_student(self.client, self.sankalp)
        b = create_student(self.client, self.pratibha)
        c = create_student(self.client, self.pragati)
        d = create_student(self.client, self.pratibha)
        self.assertEqual(a.seat_number, 1)
        self.assertEqual(b.seat_number, 2)
        self.assertEqual(c.seat_number, 2)   # afternoon shares the morning student's seat
        self.assertEqual(d.seat_number, 3)   # second morning student cannot share seat 2

    def test_manual_seat_conflict_rejected(self):
        create_student(self.client, self.sankalp)
        data = student_post_data(self.pratibha, seat_number="1")
        response = self.client.post("/students/add/", data)
        self.assertEqual(response.status_code, 200)
        self.assertIn("seat_number", response.context["form"].errors)
        self.assertEqual(Student.objects.count(), 1)

    def test_no_seat_available_blocks_registration(self):
        for n in range(1, 81):
            make_student_row(self.sankalp, seat=n)
        response = self.client.post("/students/add/", student_post_data(self.sankalp))
        self.assertEqual(response.status_code, 200)
        self.assertIn("program", response.context["form"].errors)

    def test_aadhaar_and_copy_are_compulsory_and_validated(self):
        r = self.client.post("/students/add/", student_post_data(self.pratibha, aadhaar_number=""))
        self.assertIn("aadhaar_number", r.context["form"].errors)
        r = self.client.post("/students/add/", student_post_data(self.pratibha, aadhaar_copy=""))
        self.assertIn("aadhaar_copy", r.context["form"].errors)
        from django.core.files.uploadedfile import SimpleUploadedFile
        fake = SimpleUploadedFile("x.pdf", b"not really a pdf", content_type="application/pdf")
        r = self.client.post("/students/add/", student_post_data(self.pratibha, aadhaar_copy=fake))
        self.assertIn("aadhaar_copy", r.context["form"].errors)
        big = SimpleUploadedFile("big.pdf", b"%PDF" + b"0" * (6 * 1024 * 1024), content_type="application/pdf")
        r = self.client.post("/students/add/", student_post_data(self.pratibha, aadhaar_copy=big))
        self.assertIn("aadhaar_copy", r.context["form"].errors)
        self.assertEqual(Student.objects.count(), 0)

    def test_duplicate_aadhaar_rejected(self):
        number = unique_aadhaar()
        create_student(self.client, self.pratibha, aadhaar_number=number)
        r = self.client.post("/students/add/", student_post_data(self.pragati, aadhaar_number=number))
        self.assertIn("aadhaar_number", r.context["form"].errors)

    def test_full_aadhaar_never_appears_on_pages(self):
        number = unique_aadhaar()
        s = create_student(self.client, self.pratibha, aadhaar_number=number)
        for url in ["/students/", f"/students/{s.pk}/", f"/students/{s.pk}/edit/", "/reports/students/csv/"]:
            body = self.client.get(url).content.decode("utf-8", "ignore")
            self.assertNotIn(number, body, url)
        self.assertIn(number[-4:], self.client.get(f"/students/{s.pk}/").content.decode())

    def test_fee_override_is_custom_and_batch_fee_untouched(self):
        s = create_student(self.client, self.pratibha, monthly_fee="350")
        self.assertEqual(s.custom_monthly_fee, Decimal("350"))
        self.assertEqual(s.monthly_fee, Decimal("350"))
        self.pratibha.refresh_from_db()
        self.assertEqual(self.pratibha.monthly_fee, Decimal("500"))
        self.assertEqual(s.payments.get().amount_paid, Decimal("350"))

    def test_non_admin_cannot_register(self):
        self.client.logout()
        stu = User.objects.create_user(username="stu", password="StrongPass@123", role="student")
        self.client.force_login(stu)
        self.assertEqual(self.client.get("/students/add/").status_code, 403)

    def test_batch_change_requires_confirmation_and_moves_seat(self):
        s = create_student(self.client, self.pratibha)  # seat 1 morning
        data = {k: v for k, v in student_post_data(self.sankalp, first_name=s.first_name, last_name=s.last_name,
                                                   primary_email=s.contact.primary_email).items()
                if k not in ("collect_fee", "payment_mode", "payment_reference", "aadhaar_number", "aadhaar_copy")}
        data["monthly_fee"] = "1000"
        r = self.client.post(f"/students/{s.pk}/edit/", data)
        self.assertEqual(r.status_code, 200)
        self.assertIn("confirm_batch_change", r.context["form"].errors)
        s.refresh_from_db()
        self.assertEqual(s.program, self.pratibha)
        data["confirm_batch_change"] = "on"
        r = self.client.post(f"/students/{s.pk}/edit/", data)
        self.assertEqual(r.status_code, 302, r.context["form"].errors if r.context else "")
        s.refresh_from_db()
        self.assertEqual(s.program, self.sankalp)
        self.assertEqual(s.monthly_fee, Decimal("1000"))
        self.assertEqual(s.seat_shift, "full_day")
        self.assertEqual(s.payments.count(), 1)  # old payment kept untouched
        self.assertEqual(s.payments.get().amount_paid, Decimal("500"))

    def test_seat_change_only_to_free_seats(self):
        a = create_student(self.client, self.sankalp)
        b = create_student(self.client, self.sankalp)
        r = self.client.post(f"/students/{b.pk}/seat/", {"seat": a.seat_number})
        self.assertEqual(r.status_code, 200)
        b.refresh_from_db()
        self.assertEqual(b.seat_number, 2)
        r = self.client.post(f"/students/{b.pk}/seat/", {"seat": "40"})
        self.assertEqual(r.status_code, 302)
        b.refresh_from_db()
        self.assertEqual(b.seat_number, 40)

    def test_deactivation_flow(self):
        s = create_student(self.client, self.sankalp, rfid_uid="CARD-1")
        r = self.client.post(f"/students/{s.pk}/deactivate/", {"reason": "", "confirm": "yes"})
        self.assertEqual(r.status_code, 200)
        r = self.client.post(f"/students/{s.pk}/deactivate/", {"reason": "Left the city"})
        self.assertEqual(r.status_code, 200)
        s.refresh_from_db()
        self.assertEqual(s.status, Student.Status.ACTIVE)
        r = self.client.post(f"/students/{s.pk}/deactivate/", {"reason": "Left the city", "confirm": "yes"})
        self.assertEqual(r.status_code, 302)
        s.refresh_from_db()
        self.assertEqual(s.status, Student.Status.DEACTIVATED)
        self.assertIsNone(s.seat_number)
        self.assertEqual(s.released_seat, 1)
        self.assertTrue(seats.seat_is_free(1, "full_day"))
        self.assertEqual(s.rfid_uid, "CARD-1")  # stays on record so it can never be reissued
        # the disabled card cannot be given to someone else
        r = self.client.post("/students/add/", student_post_data(self.pratibha, rfid_uid="CARD-1"))
        self.assertIn("rfid_uid", r.context["form"].errors)
        # nor can a payment bring the student back
        from fees.services import PaymentError, check_can_pay
        with self.assertRaises(PaymentError):
            check_can_pay(s)

    def test_student_delete_needs_id_and_password(self):
        s = create_student(self.client, self.pratibha)
        for data in ({"confirm_id": "WRONG", "password": "9793"}, {"confirm_id": s.student_id, "password": "bad"}):
            self.client.post(f"/students/{s.pk}/delete/", data)
            self.assertTrue(Student.objects.filter(pk=s.pk).exists())

    def test_delete_accepts_id_typed_loosely(self):
        s = make_student_row(self.pratibha, seat=None, status=Student.Status.DEACTIVATED)
        Student.objects.filter(pk=s.pk).update(student_id="1")
        r = self.client.post(f"/students/{s.pk}/delete/", {"confirm_id": " (1) ", "password": "9793"})
        self.assertEqual(r.status_code, 302)
        self.assertFalse(Student.objects.filter(pk=s.pk).exists())

    def test_student_delete_removes_everything_and_frees_seat(self):
        from audits.models import AuditLog
        from fees.models import Payment
        s = create_student(self.client, self.pratibha, collect_fee="on", payment_mode="cash")
        seat = s.seat_number
        self.assertTrue(Payment.objects.filter(student=s).exists())
        r = self.client.post(f"/students/{s.pk}/delete/", {"confirm_id": s.student_id.lower(), "password": "9793"})
        self.assertEqual(r.status_code, 302)
        self.assertFalse(Student.objects.filter(pk=s.pk).exists())
        self.assertFalse(Payment.objects.filter(student_id=s.pk).exists())
        self.assertTrue(AuditLog.objects.filter(action="student_deleted").exists())
        again = create_student(self.client, self.pratibha)
        self.assertEqual(again.seat_number, seat)

    def test_old_toggle_status_urls_are_gone(self):
        s = create_student(self.client, self.pratibha)
        self.assertEqual(self.client.get(f"/students/{s.pk}/status/inactive/").status_code, 404)


@override_settings(PRIVATE_MEDIA_ROOT=PRIVATE)
class AadhaarCopyAccessTest(TestCase):
    def setUp(self):
        self.admin = make_admin()
        self.client.force_login(self.admin)
        self.student = create_student(self.client, batch("Pratibha"))
        self.url = f"/students/{self.student.pk}/aadhaar-copy/"

    def test_copy_is_not_publicly_addressable(self):
        with self.assertRaises(ValueError):
            self.student.aadhaar_copy.url
        self.assertEqual(self.client.get("/media/" + self.student.aadhaar_copy.name).status_code, 404)

    def test_wrong_password_then_correct_password(self):
        r = self.client.post(self.url, {"password": "0000"})
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Wrong password")
        r = self.client.post(self.url, {"password": "9793"})
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r["Content-Type"].startswith("application/pdf") or r.streaming)
        self.assertEqual(b"".join(r.streaming_content)[:4], b"%PDF")

    def test_locks_after_repeated_wrong_passwords(self):
        for _ in range(5):
            self.client.post(self.url, {"password": "bad"})
        r = self.client.post(self.url, {"password": "9793"})
        self.assertContains(r, "Too many wrong attempts")

    def test_requires_admin(self):
        self.client.logout()
        self.assertEqual(self.client.get(self.url).status_code, 302)  # login redirect
        stu = User.objects.create_user(username="stu2", password="StrongPass@123", role="student")
        self.client.force_login(stu)
        self.assertEqual(self.client.post(self.url, {"password": "9793"}).status_code, 403)

    def test_views_are_audit_logged(self):
        from audits.models import AuditLog
        self.client.post(self.url, {"password": "9793"})
        self.assertTrue(AuditLog.objects.filter(action="aadhaar_copy_viewed").exists())


@override_settings(PRIVATE_MEDIA_ROOT=PRIVATE)
class PageSmokeTest(TestCase):
    """Every screen opens without errors, for the admin and for a student."""

    def setUp(self):
        self.admin = make_admin()
        self.client.force_login(self.admin)
        self.s = create_student(self.client, batch("Sankalp"), rfid_uid="SMOKE-1")

    def test_admin_pages(self):
        pk = self.s.pk
        urls = ["/", "/dashboard/", "/students/", "/students/?q=SMOKE&status=active&program=1", "/students/add/",
                f"/students/{pk}/", f"/students/{pk}/edit/", f"/students/{pk}/deactivate/", f"/students/{pk}/seat/",
                f"/students/{pk}/aadhaar-copy/", f"/students/{pk}/delete/", "/students/seats/", "/academics/",
                "/academics/programs/add/", f"/academics/programs/{batch('Pratibha').pk}/edit/", "/fees/",
                "/fees/payments/add/", f"/fees/payments/add/?student={self.s.student_id}", "/attendance/", "/audits/",
                "/fees/students/search/?q=T", "/attendance/scan/ping/"]
        for url in urls:
            r = self.client.get(url, follow=True)
            self.assertEqual(r.status_code, 200, url)

    def test_student_pages(self):
        owner = User.objects.create_user(username="stuS", password="StrongPass@123", role="student")
        self.s.user = owner
        self.s.save()
        self.client.force_login(owner)
        for url in ["/dashboard/", "/students/me/", f"/students/{self.s.pk}/", f"/students/{self.s.pk}/edit/",
                    "/fees/", "/attendance/me/"]:
            self.assertEqual(self.client.get(url).status_code, 200, url)
        for url in ["/students/", "/students/add/", "/students/seats/", f"/students/{self.s.pk}/deactivate/",
                    f"/students/{self.s.pk}/aadhaar-copy/", "/academics/", "/reports/"]:
            self.assertEqual(self.client.get(url).status_code, 403, url)

    def test_student_cannot_change_admin_only_fields_on_own_profile(self):
        owner = User.objects.create_user(username="stuT", password="StrongPass@123", role="student")
        self.s.user = owner
        self.s.save()
        self.client.force_login(owner)
        data = {"first_name": "Changed", "last_name": self.s.last_name, "mobile_number": "9000000000",
                "primary_email": self.s.contact.primary_email, "program": batch("Pratibha").pk, "monthly_fee": "1",
                "seat_number": "70", "rfid_uid": "HACK", "gender": "female"}
        self.client.post(f"/students/{self.s.pk}/edit/", data)
        self.s.refresh_from_db()
        self.assertEqual(self.s.first_name, "Changed")          # own details can change
        self.assertEqual(self.s.program.name, "Sankalp")         # batch cannot
        self.assertEqual(self.s.seat_number, 1)                  # seat cannot
        self.assertEqual(self.s.rfid_uid, "SMOKE-1")             # card cannot
        self.assertIsNone(self.s.custom_monthly_fee)             # fee cannot

    def test_batch_fee_edit_screen(self):
        p = batch("Pratibha")
        data = {"name": "Pratibha", "code": "PRATIBHA", "monthly_fee": "700", "shift": "morning",
                "start_time": "07:00", "end_time": "14:00", "is_active": "on"}
        r = self.client.post(f"/academics/programs/{p.pk}/edit/", data)
        self.assertEqual(r.status_code, 302)
        p.refresh_from_db()
        self.assertEqual(p.monthly_fee, Decimal("700"))
        data["end_time"] = "06:00"
        r = self.client.post(f"/academics/programs/{p.pk}/edit/", data)
        self.assertEqual(r.status_code, 200)
        self.assertIn("end_time", r.context["form"].errors)


@override_settings(PRIVATE_MEDIA_ROOT=PRIVATE)
class LegacyDataTest(TestCase):
    """Students created before the library features have no batch fee, seat or Aadhaar."""

    def setUp(self):
        self.admin = make_admin()
        self.client.force_login(self.admin)
        dept = Department.objects.create(name="Old", code="OLD")
        self.old_program = Program.objects.create(department=dept, name="jee", code="Q1")  # fee 0, as migrated
        self.legacy = Student.objects.create(
            student_id="001", registration_number="001", first_name="Old", last_name="Student",
            program=self.old_program, department=dept, academic_year="2025", semester="",
            enrollment_date="2025-01-01",
        )
        from .models import ContactInformation
        ContactInformation.objects.create(student=self.legacy, primary_email="old@x.com", mobile_number="9999999999")

    def test_legacy_student_pages_open_and_payment_is_blocked_until_batch_chosen(self):
        for url in ["/students/", f"/students/{self.legacy.pk}/", f"/students/{self.legacy.pk}/edit/", "/fees/",
                    f"/fees/?student_id={self.legacy.pk}", "/reports/fees/?view=student", "/students/seats/"]:
            self.assertEqual(self.client.get(url).status_code, 200, url)
        from fees.services import PaymentError, check_can_pay
        with self.assertRaises(PaymentError):
            check_can_pay(self.legacy)  # monthly fee is 0 until a batch is chosen
        self.assertEqual(self.legacy.payment_status, "Unpaid")

    def test_admin_can_move_legacy_student_into_a_batch_without_aadhaar(self):
        data = {"first_name": "Old", "last_name": "Student", "mobile_number": "9999999999", "primary_email": "old@x.com",
                "program": batch("Pragati").pk, "monthly_fee": "600", "seat_number": "", "rfid_uid": "",
                "gender": "", "confirm_batch_change": "on"}
        r = self.client.post(f"/students/{self.legacy.pk}/edit/", data)
        self.assertEqual(r.status_code, 302, r.context["form"].errors if r.context else "")
        self.legacy.refresh_from_db()
        self.assertEqual(self.legacy.program.name, "Pragati")
        self.assertEqual(self.legacy.seat_number, 1)
        self.assertEqual(self.legacy.monthly_fee, Decimal("600"))
        self.assertEqual(self.legacy.aadhaar_last4, "")  # still optional for old records

    def test_legacy_payment_without_student_link_has_a_working_receipt(self):
        from fees.models import Payment
        p = Payment.objects.create(student_id_text="", amount_paid=1000, paid_on="2025-01-01")
        self.assertTrue(p.receipt_number.startswith("RC-"))
        self.assertEqual(self.client.get(f"/fees/receipt/{p.pk}/").status_code, 200)
        self.assertEqual(self.client.get("/fees/").status_code, 200)
        self.assertEqual(self.client.get("/reports/fees/?view=receipts&date_from=2024-01-01&date_to=2026-12-31").status_code, 200)
