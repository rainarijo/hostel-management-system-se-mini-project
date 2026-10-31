from datetime import timedelta
from unittest.mock import Mock, patch

from django.test import TestCase
from django.utils import timezone

from apps.accounts.models import Role, User
from apps.complaints.models import (
    Complaint,
    ComplaintCategory,
    ComplaintStatus,
)
from apps.complaints.services import (
    InvalidComplaintTransition,
    ReopenWindowExpired,
    change_status,
    overdue_complaints,
    reopen_complaint,
)
from apps.notifications.models import NotificationOutbox
from apps.notifications.services import COMPLAINT_STATUS_CHANGED
from apps.rooms.models import Hostel, Room, RoomType
from apps.students.models import Gender, StudentProfile


class ComplaintStateServiceTests(TestCase):
    """Unit tests for FR-6.3, FR-6.4 and FR-6.5 service contracts."""

    def _complaint(
        self,
        status,
        number=None,
        resolved_at=None,
    ):
        user = User.objects.create_user(
            email=f"student-{Complaint.objects.count()}@example.com",
            password="test-password",
            role=Role.STUDENT,
        )
        student = StudentProfile.objects.create(
            user=user,
            srn=f"PES1UG24CS{Complaint.objects.count() + 1:03d}",
            name="Test Student",
            gender=Gender.MALE,
            program="Computer Science",
            year=2,
        )
        hostel = Hostel.objects.create(
            name=f"Test Hostel {Hostel.objects.count() + 1}",
            gender_type=Gender.MALE,
        )
        room = Room.objects.create(
            hostel=hostel,
            room_no=f"10{Room.objects.count() + 1}",
            floor=1,
            room_type=RoomType.SINGLE,
            capacity=1,
            annual_fee=100000,
        )
        complaint = Complaint.objects.create(
            student=student,
            room=room,
            category=ComplaintCategory.ELECTRICAL,
            description="Electrical maintenance issue requiring attention.",
            status=status,
            resolved_at=resolved_at,
        )

        if number:
            complaint.complaint_no = number
            complaint.save(update_fields=["complaint_no"])

        return complaint

    @patch("apps.complaints.services.log_action")
    def test_open_can_move_to_in_progress_with_remark(self, log_action):
        complaint = self._complaint(ComplaintStatus.OPEN)

        change_status(
            complaint,
            ComplaintStatus.IN_PROGRESS,
            "Technician assigned.",
            object(),
        )

        complaint.refresh_from_db()

        self.assertEqual(complaint.status, ComplaintStatus.IN_PROGRESS)
        self.assertEqual(complaint.remark, "Technician assigned.")
        log_action.assert_called_once()

        notification = NotificationOutbox.objects.get(
            kind=COMPLAINT_STATUS_CHANGED,
            entity_id=complaint.complaint_no,
        )
        self.assertEqual(
            notification.recipient_email,
            complaint.student.user.email,
        )
        self.assertEqual(
            notification.payload["old_status"],
            ComplaintStatus.OPEN,
        )
        self.assertEqual(
            notification.payload["new_status"],
            ComplaintStatus.IN_PROGRESS,
        )
        self.assertEqual(
            notification.payload["remark"],
            "Technician assigned.",
        )

    @patch("apps.complaints.services.log_action")
    def test_open_can_be_rejected_with_remark(self, log_action):
        complaint = self._complaint(ComplaintStatus.OPEN)

        change_status(
            complaint,
            ComplaintStatus.REJECTED,
            "Duplicate complaint.",
            object(),
        )

        complaint.refresh_from_db()

        self.assertEqual(complaint.status, ComplaintStatus.REJECTED)
        self.assertEqual(complaint.remark, "Duplicate complaint.")
        log_action.assert_called_once()

        notification = NotificationOutbox.objects.get(
            kind=COMPLAINT_STATUS_CHANGED,
            entity_id=complaint.complaint_no,
        )
        self.assertEqual(
            notification.payload["old_status"],
            ComplaintStatus.OPEN,
        )
        self.assertEqual(
            notification.payload["new_status"],
            ComplaintStatus.REJECTED,
        )

    @patch("apps.complaints.services.log_action")
    def test_in_progress_can_be_resolved_with_remark(self, log_action):
        complaint = self._complaint(ComplaintStatus.IN_PROGRESS)

        before = timezone.now()
        change_status(
            complaint,
            ComplaintStatus.RESOLVED,
            "Repair completed.",
            object(),
        )

        complaint.refresh_from_db()

        self.assertEqual(complaint.status, ComplaintStatus.RESOLVED)
        self.assertEqual(complaint.remark, "Repair completed.")
        self.assertIsNotNone(complaint.resolved_at)
        self.assertGreaterEqual(complaint.resolved_at, before)
        log_action.assert_called_once()

        notification = NotificationOutbox.objects.get(
            kind=COMPLAINT_STATUS_CHANGED,
            entity_id=complaint.complaint_no,
        )
        self.assertEqual(
            notification.payload["old_status"],
            ComplaintStatus.IN_PROGRESS,
        )
        self.assertEqual(
            notification.payload["new_status"],
            ComplaintStatus.RESOLVED,
        )

    def test_invalid_transition_is_rejected(self):
        complaint = self._complaint(ComplaintStatus.OPEN)

        with self.assertRaises(InvalidComplaintTransition):
            change_status(
                complaint,
                ComplaintStatus.RESOLVED,
                "Invalid direct resolution.",
                object(),
            )

        self.assertEqual(
            NotificationOutbox.objects.count(),
            0,
        )

    def test_status_change_requires_remark(self):
        complaint = self._complaint(ComplaintStatus.OPEN)

        with self.assertRaises(InvalidComplaintTransition):
            change_status(
                complaint,
                ComplaintStatus.IN_PROGRESS,
                "   ",
                object(),
            )

        self.assertEqual(
            NotificationOutbox.objects.count(),
            0,
        )

    @patch("apps.complaints.services.log_action")
    def test_resolved_can_be_reopened_within_seven_days(self, log_action):
        complaint = self._complaint(
            ComplaintStatus.RESOLVED,
            resolved_at=timezone.now() - timedelta(days=6),
        )

        reopen_complaint(complaint, object())

        complaint.refresh_from_db()

        self.assertEqual(complaint.status, ComplaintStatus.OPEN)
        self.assertIsNone(complaint.resolved_at)
        log_action.assert_called_once()

    def test_resolved_cannot_be_reopened_after_seven_days(self):
        complaint = self._complaint(
            ComplaintStatus.RESOLVED,
            resolved_at=timezone.now() - timedelta(days=8),
        )

        with self.assertRaises(ReopenWindowExpired):
            reopen_complaint(complaint, object())

    def test_overdue_filter_uses_72_hour_cutoff_and_statuses(self):
        queryset = Mock()
        now = timezone.now()

        overdue_complaints(queryset, now=now)

        kwargs = queryset.filter.call_args.kwargs
        self.assertEqual(
            kwargs["status__in"],
            [ComplaintStatus.OPEN, ComplaintStatus.IN_PROGRESS],
        )
        self.assertEqual(
            kwargs["created_at__lt"],
            now - timedelta(hours=72),
        )
