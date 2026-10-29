"""Tests for dashboard counts (FR-4.4, SAD DD-1 scope rule)."""
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import Role, User
from apps.allocation.models import Allocation, AllocationStatus, RoomApplication
from apps.rooms.models import Hostel, Room
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

    def test_warden_dashboard_bed_summary_is_scoped_and_handles_empty_hostels(self):
        warden = User.objects.create_user("beds-warden@hms.local", PASSWORD, role=Role.WARDEN)
        assigned = Hostel.objects.create(name="Assigned Block", gender_type="M")
        assigned.wardens.add(warden)
        other = Hostel.objects.create(name="Other Block", gender_type="M")
        Room.objects.create(hostel=assigned, room_no="101", floor=1, room_type="DOUBLE",
                            capacity=2, annual_fee=50000)
        other_room = Room.objects.create(hostel=other, room_no="201", floor=2, room_type="TRIPLE",
                                         capacity=3, annual_fee=60000)
        student_user = User.objects.create_user("beds-student@hms.local", PASSWORD, role=Role.STUDENT)
        student = StudentProfile.objects.create(
            user=student_user, srn="PES1UG24CS111", name="Bed Student", gender="M",
            program="B.Tech CSE", year=2,
        )
        Allocation.objects.create(
            student=student, room=other_room, bed_no=1, start_date=timezone.localdate(),
            status=AllocationStatus.CONFIRMED,
        )

        self.client.force_login(warden)
        response = self.client.get(reverse("core:warden_dashboard"))
        self.assertEqual(response.context["beds"], {
            "total": 2, "occupied": 0, "vacant": 2, "percent": 0,
        })

        empty_warden = User.objects.create_user("empty-warden@hms.local", PASSWORD, role=Role.WARDEN)
        Hostel.objects.create(name="Empty Warden Block", gender_type="M").wardens.add(empty_warden)
        self.client.force_login(empty_warden)
        response = self.client.get(reverse("core:warden_dashboard"))
        self.assertEqual(response.context["beds"], {
            "total": 0, "occupied": 0, "vacant": 0, "percent": 0,
        })

    def test_administrator_dashboard_bed_summary_and_overdue_complaints_are_system_wide(self):
        from datetime import timedelta

        from apps.complaints.models import Complaint, ComplaintCategory
        from apps.rooms.models import Room

        admin = User.objects.create_user("metrics-admin@hms.local", PASSWORD, role=Role.ADMIN)
        hostel = Hostel.objects.create(name="Admin Metrics Block", gender_type="M")
        room = Room.objects.create(hostel=hostel, room_no="301", floor=3, room_type="SINGLE",
                                   capacity=1, annual_fee=50000)
        student_user = User.objects.create_user("metrics-student@hms.local", PASSWORD, role=Role.STUDENT)
        student = StudentProfile.objects.create(
            user=student_user, srn="PES1UG24CS112", name="Metrics Student", gender="M",
            program="B.Tech CSE", year=2,
        )
        Allocation.objects.create(
            student=student, room=room, bed_no=1, start_date=timezone.localdate(),
            status=AllocationStatus.CONFIRMED,
        )
        complaint = Complaint.objects.create(
            student=student, room=room, category=ComplaintCategory.OTHER, description="A broken fixture.",
        )
        Complaint.objects.filter(pk=complaint.pk).update(
            created_at=timezone.now() - timedelta(hours=73),
        )

        self.client.force_login(admin)
        response = self.client.get(reverse("core:admin_dashboard"))
        self.assertEqual(response.context["beds"], {
            "total": 1, "occupied": 1, "vacant": 0, "percent": 100,
        })
        self.assertEqual(response.context["overdue_complaints"], 1)
