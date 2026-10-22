"""Test Plan TC-14 (FR-7.1, FR-7.5): fee record per allocation and the student's dues page."""
from datetime import date
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import Role, User
from apps.allocation.models import Allocation
from apps.fees.models import FeeRecord, Payment, PaymentMode
from apps.fees.services import create_fee_record
from apps.rooms.models import Hostel, Room, RoomType
from apps.students.models import StudentProfile

PASSWORD = "Hostel2026pass"


def make_student(n, gender="M"):
    user = User.objects.create_user(f"tc14student{n}@hms.local", PASSWORD, role=Role.STUDENT,
                                    first_name="Test", last_name=f"Student{n}")
    profile = StudentProfile.objects.create(
        user=user, srn=f"PES1UG24CS8{n:02d}", name=f"Test Student{n}", gender=gender, program="B.Tech CSE",
        year=2, mobile=f"98450002{n:02d}", permanent_address="12, 4th Cross, Jayanagar, Bengaluru",
        guardian_name="Parent", guardian_relationship="Parent", guardian_mobile=f"98860002{n:02d}",
        blood_group="O+")
    return user, profile


class FeeRecordTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        hostel = Hostel.objects.create(name="Fee Test Block", gender_type="M")
        cls.room = Room.objects.create(hostel=hostel, room_no="301", floor=3, room_type=RoomType.DOUBLE,
                                       capacity=2, annual_fee=75000)
        cls.user, cls.student = make_student(1)
        cls.other_user, cls.other_student = make_student(2)
        cls.warden = User.objects.create_user("tc14warden@hms.local", PASSWORD, role=Role.WARDEN,
                                              first_name="W", last_name="Arden")

    def allocate(self, student, bed_no):
        return Allocation.objects.create(student=student, room=self.room, bed_no=bed_no,
                                         start_date=date.today(), academic_year="2026-2027")

    def pay(self, allocation, amount, receipt_no):
        return Payment.objects.create(fee_record=allocation.fee_record, receipt_no=receipt_no,
                                      amount=Decimal(amount), mode=PaymentMode.CASH, paid_on=date.today(),
                                      recorded_by=self.warden)

    def test_tc14_new_allocation_gets_fee_record_equal_to_room_annual_fee(self):
        allocation = self.allocate(self.student, 1)
        record = FeeRecord.objects.get(allocation=allocation)
        self.assertEqual(record.total_amount, self.room.annual_fee)
        self.assertEqual(record.academic_year, "2026-2027")
        self.assertEqual(record.balance, record.total_amount)

    def test_tc14_create_fee_record_is_idempotent(self):
        allocation = self.allocate(self.student, 1)
        again = create_fee_record(allocation)
        self.assertEqual(FeeRecord.objects.filter(allocation=allocation).count(), 1)
        self.assertEqual(again.pk, allocation.fee_record.pk)

    def test_tc14_dues_page_shows_total_paid_balance_and_history(self):
        allocation = self.allocate(self.student, 1)
        self.pay(allocation, "20000.00", "RCP-2026-90001")
        self.client.force_login(self.user)
        response = self.client.get(reverse("fees:my_dues"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "INR 75000.00")      # total fee
        self.assertContains(response, "INR 20000.00")      # amount paid (also in the history row)
        self.assertContains(response, "INR 55000.00")      # balance
        self.assertContains(response, "RCP-2026-90001")

    def test_tc14_dues_page_without_payments_says_so(self):
        self.allocate(self.student, 1)
        self.client.force_login(self.user)
        response = self.client.get(reverse("fees:my_dues"))
        self.assertContains(response, "No payments recorded yet.")
        self.assertContains(response, "INR 75000.00")

    def test_tc14_student_sees_only_own_dues(self):
        self.allocate(self.student, 1)
        other = self.allocate(self.other_student, 2)
        self.pay(other, "5000.00", "RCP-2026-90002")
        self.client.force_login(self.user)
        response = self.client.get(reverse("fees:my_dues"))
        self.assertNotContains(response, "RCP-2026-90002")

    def test_tc14_student_without_allocation_sees_empty_message(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("fees:my_dues"))
        self.assertContains(response, "do not have a room allocation")

    def test_tc14_student_is_redirected_from_fees_index_to_dues(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("fees:index"))
        self.assertRedirects(response, reverse("fees:my_dues"))

    def test_tc14_warden_cannot_open_student_dues_page(self):
        self.client.force_login(self.warden)
        response = self.client.get(reverse("fees:my_dues"))
        self.assertEqual(response.status_code, 403)
