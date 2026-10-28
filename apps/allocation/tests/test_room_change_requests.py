"""Tests for FR-5.1 and FR-5.3 room change requests."""
from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import Role, User
from apps.allocation.models import Allocation, AllocationStatus, ChangeStatus, RoomChangeRequest
from apps.allocation.services import reject_room_change_request, submit_room_change_request
from apps.core.exceptions import BusinessRuleViolation
from apps.core.models import AuditLog
from apps.rooms.models import Hostel, Room
from apps.students.models import StudentProfile

PASSWORD = "Strongpass2026"
REQUEST_REASON = "I need a quieter room for study."
DECISION_REASON = "No suitable alternative room is currently available."


class RoomChangeRequestTests(TestCase):
    def setUp(self):
        self.warden = User.objects.create_user("warden@hms.local", PASSWORD, role=Role.WARDEN)
        self.hostel = Hostel.objects.create(name="Cauvery Block", gender_type="M")
        self.hostel.wardens.add(self.warden)
        self.room = Room.objects.create(hostel=self.hostel, room_no="101", floor=1, room_type="DOUBLE",
                                        capacity=2, annual_fee=75000)
        user = User.objects.create_user("student@hms.local", PASSWORD, role=Role.STUDENT)
        self.student = StudentProfile.objects.create(user=user, srn="PES1UG24CS001", name="Student One",
                                                     gender="M", program="B.Tech CSE", year=1)
        self.allocation = self.make_allocation()

    def make_allocation(self, status=AllocationStatus.CONFIRMED, days_ago=30):
        return Allocation.objects.create(
            student=self.student, room=self.room, bed_no=1, start_date=timezone.localdate() - timedelta(days=days_ago),
            status=status,
        )

    def submit_url(self):
        return reverse("allocation:change_requests")

    def rejection_url(self, change_request):
        return reverse("allocation:reject_change_request", args=[change_request.pk])

    def submit(self, reason=REQUEST_REASON):
        self.client.login(email=self.student.user.email, password=PASSWORD)
        return self.client.post(self.submit_url(), {"reason": reason})

    def test_fr51_student_with_confirmed_allocation_can_submit_request(self):
        response = self.submit()

        self.assertRedirects(response, self.submit_url())
        change_request = RoomChangeRequest.objects.get(student=self.student)
        self.assertEqual(change_request.from_allocation, self.allocation)
        self.assertEqual(change_request.reason, REQUEST_REASON)
        self.assertEqual(change_request.status, ChangeStatus.PENDING)
        self.assertTrue(AuditLog.objects.filter(action="ROOM_CHANGE_REQUEST_SUBMITTED",
                                                entity_id=str(change_request.pk)).exists())

    def test_fr51_reason_shorter_than_ten_characters_is_rejected(self):
        response = self.submit("Too short")

        self.assertContains(response, "Ensure this value has at least 10 characters", status_code=200)
        self.assertFalse(RoomChangeRequest.objects.exists())

    def test_fr51_reason_longer_than_300_characters_is_rejected(self):
        response = self.submit("R" * 301)

        self.assertContains(response, "Ensure this value has at most 300 characters", status_code=200)
        self.assertFalse(RoomChangeRequest.objects.exists())

    def test_fr51_student_without_confirmed_allocation_cannot_submit(self):
        self.allocation.status = AllocationStatus.PROVISIONAL
        self.allocation.save(update_fields=["status", "updated_at"])

        response = self.submit()

        self.assertContains(response, "A confirmed allocation is required", status_code=409)
        self.assertFalse(RoomChangeRequest.objects.exists())

    def test_fr51_second_pending_request_is_rejected(self):
        submit_room_change_request(self.student, REQUEST_REASON)

        response = self.submit("Another reason that is long enough.")

        self.assertContains(response, "already have a pending room change request", status_code=409)
        self.assertEqual(RoomChangeRequest.objects.filter(student=self.student).count(), 1)

    def test_fr51_30_day_wait_is_enforced_from_allocation_start(self):
        self.allocation.start_date = timezone.localdate() - timedelta(days=29)
        self.allocation.save(update_fields=["start_date", "updated_at"])

        response = self.submit()

        self.assertContains(response, "You can request a room change on or after", status_code=409)
        self.assertFalse(RoomChangeRequest.objects.exists())

    def test_fr51_exactly_30_days_of_occupancy_is_eligible(self):
        response = self.submit()

        self.assertRedirects(response, self.submit_url())
        self.assertTrue(RoomChangeRequest.objects.filter(student=self.student).exists())

    def test_fr53_authorized_warden_can_reject_pending_request(self):
        change_request = submit_room_change_request(self.student, REQUEST_REASON)
        self.client.login(email=self.warden.email, password=PASSWORD)

        response = self.client.post(self.rejection_url(change_request), {"reason": DECISION_REASON})

        self.assertRedirects(response, reverse("allocation:change_request_queue"))
        change_request.refresh_from_db()
        self.assertEqual(change_request.status, ChangeStatus.REJECTED)
        self.assertEqual(change_request.decision_reason, DECISION_REASON)
        self.assertEqual(change_request.decided_by, self.warden)
        self.assertTrue(AuditLog.objects.filter(action="ROOM_CHANGE_REQUEST_REJECTED",
                                                entity_id=str(change_request.pk)).exists())

    def test_fr53_rejection_reason_is_visible_to_student(self):
        change_request = submit_room_change_request(self.student, REQUEST_REASON)
        reject_room_change_request(change_request, DECISION_REASON, self.warden)
        self.client.login(email=self.student.user.email, password=PASSWORD)

        response = self.client.get(self.submit_url())

        self.assertContains(response, "Rejected")
        self.assertContains(response, DECISION_REASON)

    def test_fr53_missing_rejection_reason_is_rejected(self):
        change_request = submit_room_change_request(self.student, REQUEST_REASON)
        self.client.login(email=self.warden.email, password=PASSWORD)

        response = self.client.post(self.rejection_url(change_request), {"reason": "   "})

        self.assertContains(response, "This field is required", status_code=200)
        change_request.refresh_from_db()
        self.assertEqual(change_request.status, ChangeStatus.PENDING)
        self.assertEqual(change_request.decision_reason, "")

    def test_fr53_student_cannot_reject_request(self):
        change_request = submit_room_change_request(self.student, REQUEST_REASON)
        self.client.login(email=self.student.user.email, password=PASSWORD)

        response = self.client.post(self.rejection_url(change_request), {"reason": DECISION_REASON})

        self.assertEqual(response.status_code, 403)
        change_request.refresh_from_db()
        self.assertEqual(change_request.status, ChangeStatus.PENDING)

    def test_fr53_warden_outside_hostel_scope_cannot_reject_request(self):
        other_warden = User.objects.create_user("other@hms.local", PASSWORD, role=Role.WARDEN)
        Hostel.objects.create(name="Kaveri Block", gender_type="F").wardens.add(other_warden)
        change_request = submit_room_change_request(self.student, REQUEST_REASON)
        self.client.login(email=other_warden.email, password=PASSWORD)

        response = self.client.post(self.rejection_url(change_request), {"reason": DECISION_REASON})

        self.assertEqual(response.status_code, 404)
        change_request.refresh_from_db()
        self.assertEqual(change_request.status, ChangeStatus.PENDING)

    def test_fr53_request_that_is_no_longer_pending_cannot_be_rejected(self):
        change_request = submit_room_change_request(self.student, REQUEST_REASON)
        reject_room_change_request(change_request, DECISION_REASON, self.warden)

        with self.assertRaisesMessage(BusinessRuleViolation, "This room change request is no longer pending."):
            reject_room_change_request(change_request, "A second rejection reason.", self.warden)

        self.client.login(email=self.warden.email, password=PASSWORD)
        response = self.client.post(self.rejection_url(change_request), {"reason": "A second rejection reason."})

        self.assertContains(response, "no longer pending", status_code=409)
        change_request.refresh_from_db()
        self.assertEqual(change_request.status, ChangeStatus.REJECTED)
        self.assertEqual(change_request.decision_reason, DECISION_REASON)

    def test_fr53_pending_queue_is_limited_to_authorized_hostels(self):
        change_request = submit_room_change_request(self.student, REQUEST_REASON)
        self.client.login(email=self.warden.email, password=PASSWORD)

        response = self.client.get(reverse("allocation:change_request_queue"))

        self.assertContains(response, self.student.srn)
        self.assertContains(response, reverse("allocation:reject_change_request", args=[change_request.pk]))
