import tempfile
from datetime import timedelta
from decimal import Decimal

from django.test import TestCase, override_settings
from django.utils import timezone

from accounts.models import User
from students.models import Student
from students.testutils import batch, create_student, make_admin, make_student_row

from .models import Payment
from .services import PaymentError, cancel_payment, check_can_pay, record_payment

PRIVATE = tempfile.mkdtemp()


@override_settings(PRIVATE_MEDIA_ROOT=PRIVATE)
class PaymentTests(TestCase):
    def setUp(self):
        self.admin = make_admin()
        self.client.force_login(self.admin)
        self.sankalp, self.pratibha = batch("Sankalp"), batch("Pratibha")

    def _inactive_student(self, program=None):
        s = make_student_row(program or self.pratibha, seat=1, status=Student.Status.INACTIVE)
        s.subscription_end = timezone.now() - timedelta(days=3)
        s.save()
        return s

    def test_payment_must_be_the_full_monthly_fee(self):
        s = self._inactive_student()
        with self.assertRaises(PaymentError):
            check_can_pay(s, amount=Decimal("200"))
        self.assertEqual(check_can_pay(s, amount=Decimal("500")), Decimal("500"))

    def test_payment_reactivates_inactive_student_and_extends_30_days(self):
        s = self._inactive_student()
        p = record_payment(s, mode="cash", user=self.admin)
        s.refresh_from_db()
        self.assertEqual(s.status, Student.Status.ACTIVE)
        self.assertEqual(timezone.localtime(s.subscription_end).date(), timezone.localdate() + timedelta(days=30))
        self.assertEqual(p.amount_paid, Decimal("500"))
        self.assertTrue(p.receipt_number.startswith("RC-"))
        self.assertEqual(s.payment_status, "Paid")

    def test_custom_fee_is_what_gets_charged(self):
        s = self._inactive_student(self.sankalp)
        s.custom_monthly_fee = Decimal("800")
        s.save()
        self.assertEqual(record_payment(s, mode="upi", reference="UTR123", user=self.admin).amount_paid, Decimal("800"))

    def test_cannot_pay_same_30_days_twice(self):
        s = self._inactive_student()
        record_payment(s, mode="cash", user=self.admin)
        s.refresh_from_db()
        with self.assertRaises(PaymentError):
            check_can_pay(s)

    def test_early_renewal_keeps_remaining_days(self):
        s = make_student_row(self.pratibha, seat=1)
        s.subscription_end = Student._new_end(timezone.localdate() - timedelta(days=25))  # ends in 5 days
        s.save()
        end_before = timezone.localtime(s.subscription_end).date()
        record_payment(s, mode="cash", user=self.admin)
        s.refresh_from_db()
        self.assertEqual(timezone.localtime(s.subscription_end).date(), end_before + timedelta(days=30))

    def test_deactivated_student_cannot_pay(self):
        s = make_student_row(self.pratibha, status=Student.Status.DEACTIVATED)
        with self.assertRaises(PaymentError):
            record_payment(s, mode="cash", user=self.admin)

    def test_cancel_restores_previous_plan_date(self):
        s = self._inactive_student()
        before = s.subscription_end
        p = record_payment(s, mode="cash", user=self.admin)
        with self.assertRaises(PaymentError):
            cancel_payment(p, reason="  ", user=self.admin)
        cancel_payment(p, reason="Entered by mistake", user=self.admin)
        s.refresh_from_db()
        p.refresh_from_db()
        self.assertTrue(p.is_cancelled)
        self.assertEqual(s.subscription_end, before)
        self.assertEqual(s.status, Student.Status.INACTIVE)  # plan expired again -> inactive
        with self.assertRaises(PaymentError):
            cancel_payment(p, reason="again", user=self.admin)

    def test_only_latest_payment_can_be_cancelled(self):
        s = make_student_row(self.pratibha, seat=1)
        s.subscription_end = Student._new_end(timezone.localdate() - timedelta(days=29))
        s.save()
        p1 = record_payment(s, mode="cash", user=self.admin)
        s.refresh_from_db()
        s.subscription_end = timezone.now() + timedelta(days=2)
        s.save()
        p2 = record_payment(s, mode="cash", user=self.admin)
        with self.assertRaises(PaymentError):
            cancel_payment(p1, reason="x", user=self.admin)
        cancel_payment(p2, reason="x", user=self.admin)

    def test_payment_form_flow_cash_and_upi_and_receipt_page(self):
        s = self._inactive_student()
        r = self.client.post("/fees/payments/add/", {"student": s.student_id, "payment_mode": "upi",
                                                     "reference": "", "paid_on": timezone.localdate().isoformat()})
        self.assertEqual(r.status_code, 200)
        self.assertIn("reference", r.context["form"].errors)  # UTR required for UPI
        r = self.client.post("/fees/payments/add/", {"student": s.student_id, "payment_mode": "upi",
                                                     "reference": "UTR987654", "paid_on": timezone.localdate().isoformat()})
        self.assertEqual(r.status_code, 302)
        p = Payment.objects.get()
        self.assertEqual(p.payment_mode, "upi")
        page = self.client.get(f"/fees/receipt/{p.pk}/")
        self.assertContains(page, p.receipt_number)
        self.assertContains(page, "UTR987654")
        self.assertContains(page, "Print Receipt")

    def test_future_payment_date_rejected(self):
        s = self._inactive_student()
        r = self.client.post("/fees/payments/add/", {"student": s.student_id, "payment_mode": "cash", "reference": "",
                                                     "paid_on": (timezone.localdate() + timedelta(days=2)).isoformat()})
        self.assertIn("paid_on", r.context["form"].errors)

    def test_receipt_visible_only_to_admin_or_owner(self):
        s = self._inactive_student()
        owner = User.objects.create_user(username="owner1", password="StrongPass@123", role="student")
        s.user = owner
        s.save()
        p = record_payment(s, mode="cash", user=self.admin)
        other = User.objects.create_user(username="other1", password="StrongPass@123", role="student")
        self.client.force_login(other)
        self.assertEqual(self.client.get(f"/fees/receipt/{p.pk}/").status_code, 403)
        self.client.force_login(owner)
        self.assertEqual(self.client.get(f"/fees/receipt/{p.pk}/").status_code, 200)

    def test_fee_pages_render_for_admin_and_student(self):
        s = create_student(self.client, self.pratibha)
        self.assertEqual(self.client.get("/fees/").status_code, 200)
        self.assertEqual(self.client.get(f"/fees/?student_id={s.pk}").status_code, 200)
        owner = User.objects.create_user(username="owner2", password="StrongPass@123", role="student")
        s.user = owner
        s.save()
        self.client.force_login(owner)
        r = self.client.get("/fees/")
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "500")
        self.assertEqual(self.client.get("/dashboard/").status_code, 200)

    def test_legacy_fee_structure_pages_are_gone(self):
        self.assertEqual(self.client.get("/fees/structures/add/").status_code, 404)
