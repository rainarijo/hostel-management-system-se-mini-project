"""Tests for dashboard counts (FR-4.4, SAD DD-1 scope rule)."""
from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import Role, User
from apps.allocation.models import RoomApplication
from apps.rooms.models import Hostel
from apps.students.models import StudentProfile

PASSWORD = "Strongpass2026"


class DashboardCountTests(TestCase):
    def test_fr44_warden_dashboard_count_matches_queue(self):
        warden = User.objects.create_user("wb@hms.local", PASSWORD, role=Role.WARDEN)
        Hostel.objects.create(name="Boys Block", gender_type="M").wardens.add(warden)
        for n, gender in enumerate(("M", "F"), start=1):
            user = User.objects.create_user(f"s{n}@hms.local", PASSWORD, role=Role.STUDENT)
            student = StudentProfile.objects.create(user=user, srn=f"PES1UG24CS{n:03d}", name=f"Student {n}",
                                                    gender=gender, program="B.Tech CSE", year=2)
            RoomApplication.objects.create(student=student, academic_year="2026-2027", preference_1="DOUBLE",
                                           application_no=f"APP-2026-{n:05d}")

        self.client.login(email="wb@hms.local", password=PASSWORD)
        resp = self.client.get(reverse("core:warden_dashboard"))
        self.assertEqual(resp.context["pending_applications"], 1)
        queue = self.client.get(reverse("allocation:queue"))
        self.assertEqual(queue.context["page"].paginator.count, 1)
