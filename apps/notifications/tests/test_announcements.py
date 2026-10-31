"""Tests for Issue #31 / FR-9.3: hostel announcements."""
from datetime import date, timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import Role, User
from apps.allocation.models import Allocation
from apps.notifications.models import Announcement
from apps.rooms.models import Hostel, Room, RoomType
from apps.students.models import StudentProfile


PASSWORD = "Hostel2026pass"


def make_student(number):
    user = User.objects.create_user(
        f"tc31student{number}@hms.local",
        PASSWORD,
        role=Role.STUDENT,
        first_name="Test",
        last_name=f"Student{number}",
    )
    profile = StudentProfile.objects.create(
        user=user,
        srn=f"PES1UG24CS8{number:02d}",
        name=f"Test Student{number}",
        gender="M",
        program="B.Tech CSE",
        year=2,
        mobile=f"98450002{number:02d}",
        permanent_address="12, 4th Cross, Jayanagar, Bengaluru",
        guardian_name="Parent",
        guardian_relationship="Parent",
        guardian_mobile=f"98860002{number:02d}",
        blood_group="O+",
    )
    return user, profile


class AnnouncementTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.hostel = Hostel.objects.create(name="TC31 Block A", gender_type="M")
        cls.other_hostel = Hostel.objects.create(name="TC31 Block B", gender_type="M")
        cls.inactive_hostel = Hostel.objects.create(
            name="TC31 Inactive", gender_type="M", is_active=False
        )
        cls.warden = User.objects.create_user(
            "tc31warden@hms.local", PASSWORD, role=Role.WARDEN
        )
        cls.other_warden = User.objects.create_user(
            "tc31otherwarden@hms.local", PASSWORD, role=Role.WARDEN
        )
        cls.admin = User.objects.create_user(
            "tc31admin@hms.local", PASSWORD, role=Role.ADMIN
        )
        cls.hostel.wardens.add(cls.warden)
        cls.other_hostel.wardens.add(cls.other_warden)
        cls.inactive_hostel.wardens.add(cls.warden)

        cls.room = Room.objects.create(
            hostel=cls.hostel,
            room_no="201",
            floor=2,
            room_type=RoomType.DOUBLE,
            capacity=2,
            annual_fee=75000,
        )
        cls.student, cls.profile = make_student(1)
        Allocation.objects.create(
            student=cls.profile,
            room=cls.room,
            bed_no=1,
            start_date=date.today(),
            academic_year="2026-2027",
        )

        cls.index_url = reverse("notifications:index")
        cls.post_url = reverse("notifications:post_announcement")

    def test_student_sees_only_current_announcements_for_allocated_hostel(self):
        visible = Announcement.objects.create(
            hostel=self.hostel,
            title="Water shutdown",
            body="Water will be unavailable from 10:00 to 12:00.",
            expiry_date=date.today(),
            created_by=self.warden,
        )
        other = Announcement.objects.create(
            hostel=self.other_hostel,
            title="Other hostel",
            body="Not for this student.",
            expiry_date=date.today(),
            created_by=self.other_warden,
        )
        expired = Announcement.objects.create(
            hostel=self.hostel,
            title="Expired",
            body="This should not be shown.",
            expiry_date=date.today() - timedelta(days=1),
            created_by=self.warden,
        )

        self.client.force_login(self.student)
        response = self.client.get(self.index_url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, visible.title)
        self.assertNotContains(response, other.title)
        self.assertNotContains(response, expired.title)

    def test_warden_can_post_to_assigned_active_hostel(self):
        self.client.force_login(self.warden)
        response = self.client.post(
            self.post_url,
            {
                "hostel": self.hostel.pk,
                "title": "Maintenance notice",
                "body": "Maintenance is scheduled for tomorrow.",
                "expiry_date": date.today().isoformat(),
            },
        )

        self.assertRedirects(response, self.index_url)
        announcement = Announcement.objects.get(title="Maintenance notice")
        self.assertEqual(announcement.hostel, self.hostel)
        self.assertEqual(announcement.created_by, self.warden)

    def test_warden_cannot_post_to_another_wardens_hostel(self):
        self.client.force_login(self.warden)
        response = self.client.post(
            self.post_url,
            {
                "hostel": self.other_hostel.pk,
                "title": "Unauthorized",
                "body": "This must not be created.",
                "expiry_date": date.today().isoformat(),
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(Announcement.objects.filter(title="Unauthorized").exists())
        self.assertContains(response, "Select a valid choice")

    def test_warden_cannot_select_inactive_assigned_hostel(self):
        self.client.force_login(self.warden)
        response = self.client.post(
            self.post_url,
            {
                "hostel": self.inactive_hostel.pk,
                "title": "Inactive hostel",
                "body": "This must not be created.",
                "expiry_date": date.today().isoformat(),
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(Announcement.objects.filter(title="Inactive hostel").exists())

    def test_title_and_body_limits_are_enforced(self):
        self.client.force_login(self.warden)
        response = self.client.post(
            self.post_url,
            {
                "hostel": self.hostel.pk,
                "title": "T" * 101,
                "body": "B" * 2001,
                "expiry_date": date.today().isoformat(),
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(Announcement.objects.count(), 0)
        self.assertContains(response, "Ensure this value has at most 100 characters")
        self.assertContains(response, "Ensure this value has at most 2000 characters")

    def test_past_expiry_date_is_rejected(self):
        self.client.force_login(self.warden)
        response = self.client.post(
            self.post_url,
            {
                "hostel": self.hostel.pk,
                "title": "Past expiry",
                "body": "This must not be created.",
                "expiry_date": (timezone.localdate() - timedelta(days=1)).isoformat(),
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(Announcement.objects.filter(title="Past expiry").exists())
        self.assertContains(response, "Expiry date cannot be in the past.")

    def test_student_cannot_post(self):
        self.client.force_login(self.student)
        response = self.client.get(self.post_url)
        self.assertEqual(response.status_code, 403)

    def test_admin_cannot_post_or_open_announcement_page(self):
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get(self.index_url).status_code, 403)
        self.assertEqual(self.client.get(self.post_url).status_code, 403)

    def test_anonymous_user_is_sent_to_login(self):
        response = self.client.get(self.index_url)
        self.assertEqual(response.status_code, 302)
        self.assertIn("login", response["Location"])
