from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import Role, User
from apps.allocation.models import Allocation, AllocationStatus
from apps.fees.models import Payment, PaymentMode
from apps.fees.services import create_fee_record, record_payment
from apps.rooms.models import Hostel, Room, RoomType
from apps.students.models import StudentProfile


PASSWORD = "Hostel2026pass"


def make_student(n, gender="M"):
    user = User.objects.create_user(
        f"issue29student{n}@hms.local",
        PASSWORD,
        role=Role.STUDENT,
        first_name="Test",
        last_name=f"Student{n}",
    )
    profile = StudentProfile.objects.create(
        user=user,
        srn=f"PES1UG24CS9{n:02d}",
        name=f"Test Student{n}",
        gender=gender,
        program="B.Tech CSE",
        year=2,
        mobile=f"98451002{n:02d}",
        permanent_address="12, 4th Cross, Jayanagar, Bengaluru",
        guardian_name="Parent",
        guardian_relationship="Parent",
        guardian_mobile=f"98861002{n:02d}",
        blood_group="O+",
    )
    return user, profile


class Issue29PaymentTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.hostel = Hostel.objects.create(name="Issue 29 Block", gender_type="M")
        cls.room = Room.objects.create(
            hostel=cls.hostel,
            room_no="401",
            floor=4,
            room_type=RoomType.DOUBLE,
            capacity=2,
            annual_fee=75000,
        )
        cls.user, cls.student = make_student(1)
        cls.other_user, cls.other_student = make_student(2)
        cls.warden = User.objects.create_user(
            "issue29warden@hms.local", PASSWORD, role=Role.WARDEN
        )
        cls.admin = User.objects.create_user(
            "issue29admin@hms.local", PASSWORD, role=Role.ADMIN
        )
        cls.warden.hostels.add(cls.hostel)

    def allocate(self, student=None, start=None):
        allocation = Allocation.objects.create(
            student=student or self.student,
            room=self.room,
            bed_no=1 if student == self.student or student is None else 2,
            start_date=(start or timezone.localdate()),
            academic_year="2026-2027",
        )
        create_fee_record(allocation)
        return allocation

    def test_record_payment_generates_sequential_receipt(self):
        allocation = self.allocate()
        first = record_payment(
            allocation_id=allocation.pk,
            actor=self.warden,
            amount=Decimal("20000.00"),
            mode=PaymentMode.CASH,
            txn_reference="",
            paid_on=timezone.localdate(),
            submission_id="aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
        )
        second = record_payment(
            allocation_id=allocation.pk,
            actor=self.warden,
            amount=Decimal("10000.00"),
            mode=PaymentMode.CASH,
            txn_reference="",
            paid_on=timezone.localdate(),
            submission_id="bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
        )
        self.assertEqual(first.receipt_no, "RCP-2026-00001")
        self.assertEqual(second.receipt_no, "RCP-2026-00002")

    def test_non_cash_requires_transaction_reference(self):
        allocation = self.allocate()
        with self.assertRaisesMessage(Exception, "Transaction reference is required"):
            record_payment(
                allocation_id=allocation.pk,
                actor=self.warden,
                amount=Decimal("1000.00"),
                mode=PaymentMode.ONLINE,
                txn_reference="",
                paid_on=timezone.localdate(),
                submission_id="cccccccc-cccc-cccc-cccc-cccccccccccc",
            )

    def test_payment_cannot_exceed_balance(self):
        allocation = self.allocate()
        with self.assertRaisesMessage(Exception, "Amount exceeds the outstanding balance"):
            record_payment(
                allocation_id=allocation.pk,
                actor=self.warden,
                amount=Decimal("75000.01"),
                mode=PaymentMode.CASH,
                txn_reference="",
                paid_on=timezone.localdate(),
                submission_id="dddddddd-dddd-dddd-dddd-dddddddddddd",
            )

    def test_future_payment_date_rejected(self):
        allocation = self.allocate()
        with self.assertRaisesMessage(Exception, "Payment date cannot be in the future"):
            record_payment(
                allocation_id=allocation.pk,
                actor=self.warden,
                amount=Decimal("1000.00"),
                mode=PaymentMode.CASH,
                txn_reference="",
                paid_on=timezone.localdate() + timedelta(days=1),
                submission_id="eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee",
            )

    def test_full_payment_confirms_provisional_allocation(self):
        allocation = self.allocate()
        payment = record_payment(
            allocation_id=allocation.pk,
            actor=self.warden,
            amount=Decimal("75000.00"),
            mode=PaymentMode.DD,
            txn_reference="DD12345",
            paid_on=timezone.localdate(),
            submission_id="ffffffff-ffff-ffff-ffff-ffffffffffff",
        )
        allocation.refresh_from_db()
        self.assertEqual(payment.amount, Decimal("75000.00"))
        self.assertEqual(allocation.status, AllocationStatus.CONFIRMED)

    def test_duplicate_submission_returns_existing_payment(self):
        allocation = self.allocate()
        submission = "11111111-1111-1111-1111-111111111111"
        first = record_payment(
            allocation_id=allocation.pk,
            actor=self.warden,
            amount=Decimal("5000.00"),
            mode=PaymentMode.CASH,
            txn_reference="",
            paid_on=timezone.localdate(),
            submission_id=submission,
        )
        second = record_payment(
            allocation_id=allocation.pk,
            actor=self.warden,
            amount=Decimal("5000.00"),
            mode=PaymentMode.CASH,
            txn_reference="",
            paid_on=timezone.localdate(),
            submission_id=submission,
        )
        self.assertEqual(first.pk, second.pk)
        self.assertEqual(Payment.objects.filter(fee_record=allocation.fee_record).count(), 1)

    def test_student_can_download_own_receipt(self):
        allocation = self.allocate()
        payment = record_payment(
            allocation_id=allocation.pk,
            actor=self.warden,
            amount=Decimal("1000.00"),
            mode=PaymentMode.CASH,
            txn_reference="",
            paid_on=timezone.localdate(),
            submission_id="22222222-2222-2222-2222-222222222222",
        )
        self.client.force_login(self.user)
        response = self.client.get(
            reverse("fees:receipt", args=[payment.receipt_no])
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertTrue(response.content.startswith(b"%PDF"))

    def test_student_cannot_download_other_students_receipt(self):
        allocation = self.allocate()
        payment = record_payment(
            allocation_id=allocation.pk,
            actor=self.warden,
            amount=Decimal("1000.00"),
            mode=PaymentMode.CASH,
            txn_reference="",
            paid_on=timezone.localdate(),
            submission_id="33333333-3333-3333-3333-333333333333",
        )
        self.client.force_login(self.other_user)
        response = self.client.get(
            reverse("fees:receipt", args=[payment.receipt_no])
        )
        self.assertEqual(response.status_code, 403)

    def test_provisional_unpaid_after_15_days_is_listed(self):
        allocation = self.allocate(start=timezone.localdate() - timedelta(days=16))
        Allocation.objects.filter(pk=allocation.pk).update(
            created_at=timezone.now() - timedelta(days=16)
        )
        self.client.force_login(self.warden)
        response = self.client.get(reverse("fees:provisional_unpaid"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, allocation.student.srn)

    def test_warden_cannot_manage_unassigned_hostel(self):
        allocation = self.allocate()
        other_hostel = Hostel.objects.create(name="Other Block", gender_type="M")
        other_room = Room.objects.create(
            hostel=other_hostel,
            room_no="402",
            floor=4,
            room_type=RoomType.DOUBLE,
            capacity=2,
            annual_fee=75000,
        )
        allocation.room = other_room
        allocation.save(update_fields=["room"])
        self.client.force_login(self.warden)
        response = self.client.get(
            reverse("fees:payment", args=[allocation.pk])
        )
        self.assertEqual(response.status_code, 403)
