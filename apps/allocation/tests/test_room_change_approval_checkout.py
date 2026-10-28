"""Tests for FR-5.2 atomic room changes and FR-5.4 check-out."""
from datetime import timedelta
from decimal import Decimal
from unittest import mock

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import Role, User
from apps.allocation.models import (Allocation, AllocationStatus, ChangeStatus, RoomChangeRequest)
from apps.allocation.services import (approve_room_change_request, check_out_allocation,
                                      get_active_allocation_for_warden)
from apps.core.exceptions import (AccessDenied, BedUnavailable, BusinessRuleViolation,
                                  GenderMismatch, ObjectNotFound, ValidationFailure)
from apps.core.models import AuditLog
from apps.fees.models import FeeRecord, Payment, PaymentMode
from apps.rooms.models import Hostel, Room, RoomStatus
from apps.students.models import StudentProfile

PASSWORD = "Strongpass2026"
REQUEST_REASON = "I need a quieter room for study."


class AtomicRoomChangeTests(TestCase):
    def setUp(self):
        self.warden = User.objects.create_user("warden14@hms.local", PASSWORD, role=Role.WARDEN)
        self.admin = User.objects.create_user("admin14@hms.local", PASSWORD, role=Role.ADMIN)
        self.hostel = Hostel.objects.create(name="Room Change Block", gender_type="M")
        self.hostel.wardens.add(self.warden)
        self.old_room = self.make_room("101", 1, "75000.00")
        self.destination = self.make_room("102", 1, "65000.00")
        student_user = User.objects.create_user("student14@hms.local", PASSWORD, role=Role.STUDENT)
        self.student = StudentProfile.objects.create(user=student_user, srn="PES1UG24CS014", name="Student Fourteen",
                                                     gender="M", program="B.Tech CSE", year=2)
        self.old_allocation = Allocation.objects.create(
            student=self.student, room=self.old_room, bed_no=1, start_date=timezone.localdate() - timedelta(days=40),
            academic_year="2026-2027", status=AllocationStatus.CONFIRMED,
        )
        self.change_request = RoomChangeRequest.objects.create(
            student=self.student, from_allocation=self.old_allocation, reason=REQUEST_REASON,
        )
        self.old_room.status = RoomStatus.FULL
        self.old_room.save(update_fields=["status", "updated_at"])

    def make_room(self, room_no, capacity, annual_fee, hostel=None):
        return Room.objects.create(hostel=hostel or self.hostel, room_no=room_no, floor=1, room_type="DOUBLE",
                                   capacity=capacity, annual_fee=Decimal(annual_fee))

    def approve(self, room=None, bed_no=1, actor=None, change_request=None):
        return approve_room_change_request(
            change_request or self.change_request, room or self.destination, bed_no, actor or self.warden,
        )

    def test_fr52_approval_ends_old_allocation_and_creates_replacement(self):
        replacement = self.approve()

        self.old_allocation.refresh_from_db()
        self.change_request.refresh_from_db()
        self.assertEqual(self.old_allocation.status, AllocationStatus.ENDED)
        self.assertEqual(self.old_allocation.end_date, timezone.localdate())
        self.assertEqual(self.old_allocation.end_reason, "Room change approved")
        self.assertEqual(replacement.student, self.student)
        self.assertEqual(replacement.room, self.destination)
        self.assertEqual(replacement.bed_no, 1)
        self.assertEqual(replacement.status, AllocationStatus.PROVISIONAL)
        self.assertEqual(self.change_request.status, ChangeStatus.APPROVED)
        self.assertEqual(self.change_request.decided_by, self.warden)
        self.assertTrue(AuditLog.objects.filter(action="ROOM_CHANGE_REQUEST_APPROVED",
                                                entity_id=str(self.change_request.pk)).exists())

    def test_fr52_failure_during_replacement_creation_rolls_back_old_allocation(self):
        with mock.patch("apps.allocation.services.Allocation.objects.create",
                        side_effect=RuntimeError("simulated allocation insert failure")):
            with self.assertRaisesMessage(RuntimeError, "simulated allocation insert failure"):
                self.approve()

        self.old_allocation.refresh_from_db()
        self.change_request.refresh_from_db()
        self.assertEqual(self.old_allocation.status, AllocationStatus.CONFIRMED)
        self.assertIsNone(self.old_allocation.end_date)
        self.assertFalse(Allocation.objects.active().filter(room=self.destination).exists())
        self.assertEqual(self.change_request.status, ChangeStatus.PENDING)

    def test_fr52_failure_after_fee_move_rolls_back_allocation_and_destination_bed(self):
        with mock.patch("apps.fees.services.move_fee_record", side_effect=RuntimeError("fee update failed")):
            with self.assertRaisesMessage(RuntimeError, "fee update failed"):
                self.approve()

        self.old_allocation.refresh_from_db()
        self.change_request.refresh_from_db()
        self.destination.refresh_from_db()
        self.assertEqual(self.old_allocation.status, AllocationStatus.CONFIRMED)
        self.assertEqual(self.change_request.status, ChangeStatus.PENDING)
        self.assertFalse(Allocation.objects.active().filter(room=self.destination, bed_no=1).exists())
        self.assertEqual(FeeRecord.objects.filter(allocation=self.old_allocation).count(), 1)
        self.assertEqual(self.destination.status, RoomStatus.AVAILABLE)

    def test_fr52_unavailable_bed_is_rejected_without_ending_old_allocation(self):
        other_user = User.objects.create_user("occupant14@hms.local", PASSWORD, role=Role.STUDENT)
        other_student = StudentProfile.objects.create(
            user=other_user, srn="PES1UG24CS015", name="Student Fifteen", gender="M",
            program="B.Tech CSE", year=2,
        )
        Allocation.objects.create(student=other_student, room=self.destination, bed_no=1,
                                  start_date=timezone.localdate(), status=AllocationStatus.CONFIRMED)

        with self.assertRaises(BedUnavailable):
            self.approve()

        self.old_allocation.refresh_from_db()
        self.assertEqual(self.old_allocation.status, AllocationStatus.CONFIRMED)

    def test_fr52_bed_outside_capacity_is_rejected(self):
        with self.assertRaises(ValidationFailure):
            self.approve(bed_no=2)

        self.old_allocation.refresh_from_db()
        self.assertEqual(self.old_allocation.status, AllocationStatus.CONFIRMED)

    def test_fr52_gender_mismatch_is_rejected(self):
        girls_hostel = Hostel.objects.create(name="Girls Change Block", gender_type="F")
        girls_room = self.make_room("201", 1, "65000.00", hostel=girls_hostel)

        with self.assertRaises(GenderMismatch):
            self.approve(room=girls_room, actor=self.admin)

        self.old_allocation.refresh_from_db()
        self.assertEqual(self.old_allocation.status, AllocationStatus.CONFIRMED)

    def test_fr52_student_and_out_of_scope_warden_are_denied(self):
        with self.assertRaises(AccessDenied):
            self.approve(actor=self.student.user)

        self.client.force_login(self.student.user)
        response = self.client.post(
            reverse("allocation:approve_change_request", args=[self.change_request.pk]),
            {"destination_bed": f"{self.destination.pk}:1"},
        )
        self.assertEqual(response.status_code, 403)

        other_warden = User.objects.create_user("otherwarden14@hms.local", PASSWORD, role=Role.WARDEN)
        other_hostel = Hostel.objects.create(name="Other Change Block", gender_type="M")
        other_hostel.wardens.add(other_warden)
        with self.assertRaises(ObjectNotFound):
            self.approve(actor=other_warden)
        self.client.force_login(other_warden)
        response = self.client.post(
            reverse("allocation:approve_change_request", args=[self.change_request.pk]),
            {"destination_bed": f"{self.destination.pk}:1"},
        )
        self.assertEqual(response.status_code, 404)

    def test_fr52_non_pending_request_cannot_be_approved(self):
        self.change_request.status = ChangeStatus.REJECTED
        self.change_request.save(update_fields=["status", "updated_at"])

        with self.assertRaisesMessage(BusinessRuleViolation, "no longer pending"):
            self.approve()

        self.assertEqual(Allocation.objects.active().filter(student=self.student).get(), self.old_allocation)

    def test_fr52_database_constraint_protects_against_concurrent_bed_claim(self):
        other_user = User.objects.create_user("raceoccupant14@hms.local", PASSWORD, role=Role.STUDENT)
        other_student = StudentProfile.objects.create(
            user=other_user, srn="PES1UG24CS016", name="Student Sixteen", gender="M",
            program="B.Tech CSE", year=2,
        )
        Allocation.objects.create(student=other_student, room=self.destination, bed_no=1,
                                  start_date=timezone.localdate(), status=AllocationStatus.CONFIRMED)
        with mock.patch("apps.allocation.services._bed_is_held", return_value=False):
            with self.assertRaises(BedUnavailable):
                self.approve()

        self.old_allocation.refresh_from_db()
        self.assertEqual(self.old_allocation.status, AllocationStatus.CONFIRMED)
        self.assertEqual(Allocation.objects.active().filter(room=self.destination, bed_no=1).count(), 1)

    def test_fr52_fee_record_and_payments_are_preserved_and_total_is_updated(self):
        fee_record = self.old_allocation.fee_record
        payment = Payment.objects.create(
            fee_record=fee_record, receipt_no="RCP-2026-14001", amount=Decimal("70000.00"),
            mode=PaymentMode.CASH, paid_on=timezone.localdate(), recorded_by=self.warden,
        )

        replacement = self.approve()

        fee_record.refresh_from_db()
        payment.refresh_from_db()
        self.assertEqual(fee_record.pk, replacement.fee_record.pk)
        self.assertEqual(fee_record.allocation, replacement)
        self.assertEqual(fee_record.total_amount, Decimal("65000.00"))
        self.assertEqual(payment.fee_record_id, fee_record.pk)
        self.assertEqual(replacement.status, AllocationStatus.CONFIRMED)

    def test_fr52_insufficient_payment_keeps_replacement_provisional(self):
        Payment.objects.create(
            fee_record=self.old_allocation.fee_record, receipt_no="RCP-2026-14002",
            amount=Decimal("64000.00"), mode=PaymentMode.CASH, paid_on=timezone.localdate(),
            recorded_by=self.warden,
        )

        replacement = self.approve()

        self.assertEqual(replacement.status, AllocationStatus.PROVISIONAL)
        self.assertEqual(replacement.fee_record.balance, Decimal("1000.00"))

    def test_fr52_both_room_statuses_are_recomputed(self):
        replacement = self.approve()

        self.old_room.refresh_from_db()
        self.destination.refresh_from_db()
        self.assertEqual(self.old_room.status, RoomStatus.AVAILABLE)
        self.assertEqual(self.destination.status, RoomStatus.FULL)
        self.assertEqual(self.old_room.occupancy, 0)
        self.assertEqual(self.destination.occupancy, 1)
        self.assertEqual(replacement.status, AllocationStatus.PROVISIONAL)

    def test_fr52_warden_approval_view_selects_destination_bed(self):
        self.client.force_login(self.warden)
        page = self.client.get(reverse("allocation:approve_change_request", args=[self.change_request.pk]))
        self.assertContains(page, self.destination.room_no)

        response = self.client.post(
            reverse("allocation:approve_change_request", args=[self.change_request.pk]),
            {"destination_bed": f"{self.destination.pk}:1"},
        )

        self.assertRedirects(response, reverse("allocation:change_request_queue"))
        self.assertEqual(self.change_request.__class__.objects.get(pk=self.change_request.pk).status,
                         ChangeStatus.APPROVED)


class CheckOutTests(TestCase):
    def setUp(self):
        self.warden = User.objects.create_user("checkoutwarden@hms.local", PASSWORD, role=Role.WARDEN)
        self.hostel = Hostel.objects.create(name="Check Out Block", gender_type="M")
        self.hostel.wardens.add(self.warden)
        self.room = Room.objects.create(hostel=self.hostel, room_no="301", floor=3, room_type="DOUBLE",
                                        capacity=1, annual_fee=Decimal("75000.00"), status=RoomStatus.FULL)
        self.user = User.objects.create_user("checkoutstudent@hms.local", PASSWORD, role=Role.STUDENT)
        self.student = StudentProfile.objects.create(
            user=self.user, srn="PES1UG24CS017", name="Student Seventeen", gender="M",
            program="B.Tech CSE", year=2,
        )
        self.allocation = Allocation.objects.create(
            student=self.student, room=self.room, bed_no=1,
            start_date=timezone.localdate() - timedelta(days=10), status=AllocationStatus.CONFIRMED,
        )

    def test_fr54_authorized_warden_checks_out_student_and_releases_bed(self):
        checkout_date = timezone.localdate() - timedelta(days=1)

        result = check_out_allocation(self.allocation, checkout_date, self.warden)

        self.allocation.refresh_from_db()
        self.room.refresh_from_db()
        self.assertEqual(result.status, AllocationStatus.ENDED)
        self.assertEqual(self.allocation.end_date, checkout_date)
        self.assertEqual(self.allocation.end_reason, "Student checked out")
        self.assertEqual(self.room.occupancy, 0)
        self.assertEqual(self.room.status, RoomStatus.AVAILABLE)
        self.assertTrue(AuditLog.objects.filter(action="CHECK_OUT", entity_id=str(self.allocation.pk)).exists())

    def test_fr54_future_checkout_date_is_rejected(self):
        with self.assertRaisesMessage(ValidationFailure, "cannot be in the future"):
            check_out_allocation(self.allocation, timezone.localdate() + timedelta(days=1), self.warden)

        self.allocation.refresh_from_db()
        self.assertEqual(self.allocation.status, AllocationStatus.CONFIRMED)

    def test_fr54_active_allocation_list_is_visible_to_assigned_warden(self):
        self.client.force_login(self.warden)

        response = self.client.get(reverse("allocation:active_allocations"))

        self.assertContains(response, self.student.srn)
        self.assertContains(response, reverse("allocation:check_out", args=[self.allocation.pk]))

    def test_fr54_checkout_date_before_allocation_start_is_rejected(self):
        with self.assertRaisesMessage(ValidationFailure, "cannot be before the allocation start date"):
            check_out_allocation(self.allocation, self.allocation.start_date - timedelta(days=1), self.warden)

        self.allocation.refresh_from_db()
        self.assertEqual(self.allocation.status, AllocationStatus.CONFIRMED)

    def test_fr54_repeated_checkout_is_rejected(self):
        check_out_allocation(self.allocation, timezone.localdate(), self.warden)

        with self.assertRaisesMessage(BusinessRuleViolation, "no longer active"):
            check_out_allocation(self.allocation, timezone.localdate(), self.warden)

    def test_fr54_checkout_view_rejects_future_date(self):
        self.client.force_login(self.warden)
        response = self.client.post(
            reverse("allocation:check_out", args=[self.allocation.pk]),
            {"checkout_date": (timezone.localdate() + timedelta(days=1)).isoformat()},
        )

        self.assertContains(response, "Check-out date cannot be in the future", status_code=200)
        self.allocation.refresh_from_db()
        self.assertEqual(self.allocation.status, AllocationStatus.CONFIRMED)

    def test_fr54_student_cannot_checkout_and_out_of_scope_warden_cannot_view(self):
        self.client.force_login(self.user)
        self.assertEqual(self.client.post(reverse("allocation:check_out", args=[self.allocation.pk]),
                                          {"checkout_date": timezone.localdate().isoformat()}).status_code, 403)

        other_warden = User.objects.create_user("othercheckoutwarden@hms.local", PASSWORD, role=Role.WARDEN)
        other_hostel = Hostel.objects.create(name="Other Check Out Block", gender_type="M")
        other_hostel.wardens.add(other_warden)
        self.client.force_login(other_warden)
        self.assertEqual(self.client.get(reverse("allocation:check_out", args=[self.allocation.pk])).status_code, 404)

    def test_fr54_failed_room_refresh_rolls_back_checkout(self):
        with mock.patch("apps.rooms.models.Room.refresh_status", side_effect=RuntimeError("room refresh failed")):
            with self.assertRaisesMessage(RuntimeError, "room refresh failed"):
                check_out_allocation(self.allocation, timezone.localdate(), self.warden)

        self.allocation.refresh_from_db()
        self.room.refresh_from_db()
        self.assertEqual(self.allocation.status, AllocationStatus.CONFIRMED)
        self.assertEqual(self.room.status, RoomStatus.FULL)
        self.assertEqual(self.room.occupancy, 1)

    def test_fr54_admin_is_not_authorized_to_check_out(self):
        admin = User.objects.create_user("checkoutadmin@hms.local", PASSWORD, role=Role.ADMIN)

        with self.assertRaises(AccessDenied):
            check_out_allocation(self.allocation, timezone.localdate(), admin)

    def test_fr54_inactive_allocation_is_not_in_warden_checkout_list(self):
        self.allocation.status = AllocationStatus.ENDED
        self.allocation.save(update_fields=["status", "updated_at"])

        with self.assertRaises(ObjectNotFound):
            get_active_allocation_for_warden(self.allocation.pk, self.warden)
