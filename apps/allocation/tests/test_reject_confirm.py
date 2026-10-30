"""Tests for FR-4.8 reject, FR-4.9 confirm, FR-4.10 notify (SAD 4.2.2, 4.3.3)."""
from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import Role, User
from apps.allocation.models import Allocation, AllocationStatus, ApplicationStatus, RoomApplication
from apps.allocation.services import allocate, confirm, reject
from apps.core.exceptions import BedUnavailable, BusinessRuleViolation, InvalidTransition, ValidationFailure
from apps.core.models import AuditLog
from apps.notifications.models import NotificationOutbox, OutboxStatus
from apps.notifications.services import APPLICATION_ALLOCATED, APPLICATION_REJECTED
from apps.rooms.models import Hostel, Room
from apps.students.models import StudentProfile

PASSWORD = "Strongpass2026"
REASON = "No matching room type is available this year."


class RejectConfirmTests(TestCase):
    def setUp(self):
        self.n = 0
        self.warden = User.objects.create_user("wb@hms.local", PASSWORD, role=Role.WARDEN)
        self.boys = Hostel.objects.create(name="Cauvery Block", gender_type="M")
        self.boys.wardens.add(self.warden)
        self.room = Room.objects.create(
            hostel=self.boys,
            room_no="101",
            floor=1,
            room_type="SINGLE",
            capacity=1,
            annual_fee=80000,
        )
        self.application = self.make_application()

    def make_application(self, gender="M"):
        self.n += 1
        user = User.objects.create_user(
            f"s{self.n}@hms.local",
            PASSWORD,
            role=Role.STUDENT,
        )
        student = StudentProfile.objects.create(
            user=user,
            srn=f"PES1UG24CS{self.n:03d}",
            name=f"Student {self.n}",
            gender=gender,
            program="B.Tech CSE",
            year=1,
        )
        return RoomApplication.objects.create(
            student=student,
            academic_year="2026-2027",
            preference_1="SINGLE",
            application_no=f"APP-2026-{self.n:05d}",
        )

    def assert_pending(self, application=None):
        application = application or self.application
        application.refresh_from_db()
        self.assertEqual(application.status, ApplicationStatus.PENDING)
        self.assertEqual(application.rejection_reason, "")

    def reject_url(self, application=None):
        return reverse("allocation:reject", args=[(application or self.application).pk])

    # FR-4.8
    def test_fr48_warden_rejects_with_reason(self):
        result = reject(self.application, f"  {REASON}  ", self.warden)
        self.assertEqual(result.status, ApplicationStatus.REJECTED)
        self.application.refresh_from_db()
        self.assertEqual(self.application.status, ApplicationStatus.REJECTED)
        self.assertEqual(self.application.rejection_reason, REASON)
        self.assertTrue(
            AuditLog.objects.filter(
                action="REJECT",
                entity_id=str(self.application.pk),
                new_value="application REJECTED",
            ).exists()
        )
        row = NotificationOutbox.objects.get(kind=APPLICATION_REJECTED)
        self.assertEqual(row.recipient_email, "s1@hms.local")
        self.assertEqual(row.status, OutboxStatus.PENDING)
        self.assertEqual(row.payload["reason"], REASON)
        self.assertEqual(NotificationOutbox.objects.count(), 1)

    def test_fr48_short_reason_rejected(self):
        with self.assertRaisesMessage(
            ValidationFailure,
            "Enter a reason of at least 10 characters.",
        ):
            reject(self.application, "Too short", self.warden)  # 9 characters
        with self.assertRaises(ValidationFailure):
            reject(self.application, "   short     ", self.warden)  # padding does not count
        self.assert_pending()
        self.assertFalse(NotificationOutbox.objects.exists())

    def test_fr48_cannot_reject_non_pending(self):
        allocate(self.application, self.room, 1, self.warden)
        with self.assertRaisesMessage(
            BusinessRuleViolation,
            "This application is no longer pending.",
        ):
            reject(self.application, REASON, self.warden)
        self.application.refresh_from_db()
        self.assertEqual(self.application.status, ApplicationStatus.ALLOCATED)
        self.assertFalse(
            NotificationOutbox.objects.filter(kind=APPLICATION_REJECTED).exists()
        )

    def test_fr48_warden_outside_scope_gets_404(self):
        girls_warden = User.objects.create_user(
            "wg@hms.local",
            PASSWORD,
            role=Role.WARDEN,
        )
        Hostel.objects.create(
            name="Kaveri Block",
            gender_type="F",
        ).wardens.add(girls_warden)
        self.client.login(email="wg@hms.local", password=PASSWORD)
        self.assertEqual(
            self.client.post(
                self.reject_url(),
                {"reason": REASON},
            ).status_code,
            404,
        )
        self.assert_pending()

    def test_fr48_student_gets_403(self):
        self.client.login(email="s1@hms.local", password=PASSWORD)
        self.assertEqual(
            self.client.post(
                self.reject_url(),
                {"reason": REASON},
            ).status_code,
            403,
        )
        self.assert_pending()

    def test_fr48_view_short_reason_shows_field_error_200(self):
        self.client.login(email="wb@hms.local", password=PASSWORD)
        resp = self.client.post(
            self.reject_url(),
            {"reason": "Too short"},
        )
        self.assertContains(
            resp,
            "Enter a reason of at least 10 characters.",
            status_code=200,
        )
        self.assertContains(resp, "Too short")
        self.assert_pending()

    def test_fr48_view_non_pending_shows_banner_409(self):
        allocate(self.application, self.room, 1, self.warden)
        self.client.login(email="wb@hms.local", password=PASSWORD)
        resp = self.client.post(
            self.reject_url(),
            {"reason": REASON},
        )
        self.assertContains(
            resp,
            "This application is no longer pending.",
            status_code=409,
        )

    def test_fr48_view_success_redirects_to_queue(self):
        self.client.login(email="wb@hms.local", password=PASSWORD)
        queue = self.client.get(reverse("allocation:queue"))
        self.assertContains(
            queue,
            f'data-bs-target="#reject-{self.application.pk}"',
        )
        resp = self.client.post(
            self.reject_url(),
            {"reason": REASON},
            follow=True,
        )
        self.assertRedirects(resp, reverse("allocation:queue"))
        self.assertContains(
            resp,
            f"Application {self.application.application_no} rejected.",
        )
        self.assertEqual(self.client.get(self.reject_url()).status_code, 405)

    def test_fr48_student_sees_rejection_reason(self):
        reject(self.application, REASON, self.warden)
        self.client.login(email="s1@hms.local", password=PASSWORD)
        page = self.client.get(
            reverse(
                "allocation:application_detail",
                args=[self.application.application_no],
            )
        )
        self.assertContains(page, "Rejected")
        self.assertContains(page, REASON)

    # FR-4.9
    def test_fr49_confirm_provisional_allocation(self):
        allocation = allocate(self.application, self.room, 1, self.warden)
        confirmed = confirm(allocation)
        self.assertEqual(confirmed.status, AllocationStatus.CONFIRMED)
        allocation.refresh_from_db()
        self.assertEqual(allocation.status, AllocationStatus.CONFIRMED)
        self.assertTrue(
            AuditLog.objects.filter(
                action="CONFIRM",
                entity_id=str(allocation.pk),
            ).exists()
        )

    def test_fr49_confirm_twice_raises_invalid_transition(self):
        allocation = confirm(
            allocate(self.application, self.room, 1, self.warden)
        )
        with self.assertRaises(InvalidTransition):
            confirm(allocation)
        self.assertEqual(AuditLog.objects.filter(action="CONFIRM").count(), 1)

    def test_fr49_student_sees_allocation_status(self):
        allocation = allocate(self.application, self.room, 1, self.warden)
        self.client.login(email="s1@hms.local", password=PASSWORD)
        url = reverse(
            "allocation:application_detail",
            args=[self.application.application_no],
        )
        page = self.client.get(url)
        for text in ("Cauvery Block", "101", "Provisional"):
            self.assertContains(page, text)
        confirm(allocation)
        page = self.client.get(url)
        self.assertContains(page, "Confirmed")
        self.assertNotContains(page, "Provisional")

    # FR-4.10
    def test_fr410_allocate_enqueues_allocated_email(self):
        allocate(self.application, self.room, 1, self.warden)
        row = NotificationOutbox.objects.get(kind=APPLICATION_ALLOCATED)
        self.assertEqual(row.recipient_email, "s1@hms.local")
        self.assertEqual(row.status, OutboxStatus.PENDING)
        self.assertEqual(
            row.payload,
            {
                "entity_id": self.application.application_no,
                "application_no": self.application.application_no,
                "hostel": "Cauvery Block",
                "room": "101",
                "bed": 1,
                "status": "Provisional",
                "name": "Student 1",
            },
        )

    def test_fr410_failed_allocation_enqueues_nothing(self):
        allocate(self.application, self.room, 1, self.warden)
        second = self.make_application()
        with self.assertRaises(BedUnavailable):
            allocate(second, self.room, 1, self.warden)
        self.assertEqual(NotificationOutbox.objects.count(), 1)
        self.assertFalse(Allocation.objects.filter(application=second).exists())
