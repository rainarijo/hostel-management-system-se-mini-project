"""Tests for FR-5.5 student and staff allocation history."""
from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import Role, User
from apps.allocation.models import Allocation, AllocationStatus
from apps.rooms.models import Hostel, Room
from apps.students.models import StudentProfile

PASSWORD = "Strongpass2026"


class AllocationHistoryTests(TestCase):
    def setUp(self):
        self.warden = User.objects.create_user("historywarden@hms.local", PASSWORD, role=Role.WARDEN)
        self.admin = User.objects.create_user("historyadmin@hms.local", PASSWORD, role=Role.ADMIN)
        self.student_user = User.objects.create_user("historystudent@hms.local", PASSWORD, role=Role.STUDENT)
        self.other_user = User.objects.create_user("historyother@hms.local", PASSWORD, role=Role.STUDENT)
        self.student = self.make_student(self.student_user, 21, "History Student")
        self.other_student = self.make_student(self.other_user, 22, "Other Student")

        self.hostel = Hostel.objects.create(name="History Block", gender_type="M")
        self.hostel.wardens.add(self.warden)
        self.other_hostel = Hostel.objects.create(name="Other History Block", gender_type="M")
        self.room = self.make_room(self.hostel, "101")
        self.other_room = self.make_room(self.other_hostel, "201")

        today = timezone.localdate()
        self.ended = Allocation.objects.create(
            student=self.student, room=self.room, bed_no=1, start_date=today - timedelta(days=100),
            end_date=today - timedelta(days=10), end_reason="Room change approved",
            status=AllocationStatus.ENDED,
        )
        self.current = Allocation.objects.create(
            student=self.student, room=self.room, bed_no=2, start_date=today - timedelta(days=10),
            status=AllocationStatus.CONFIRMED,
        )
        self.out_of_scope = Allocation.objects.create(
            student=self.other_student, room=self.other_room, bed_no=1,
            start_date=today - timedelta(days=30), end_date=today - timedelta(days=5),
            end_reason="Student checked out", status=AllocationStatus.ENDED,
        )

    def make_student(self, user, number, name):
        return StudentProfile.objects.create(
            user=user, srn=f"PES1UG24CS{number:03d}", name=name, gender="M",
            program="B.Tech CSE", year=2,
        )

    def make_room(self, hostel, room_no):
        return Room.objects.create(hostel=hostel, room_no=room_no, floor=1, room_type="DOUBLE",
                                   capacity=2, annual_fee=75000)

    def test_fr55_student_sees_own_current_and_ended_allocation_details(self):
        self.client.force_login(self.student_user)

        response = self.client.get(reverse("allocation:history"))

        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn("Room change approved", content)
        self.assertIn("History Block - 101", content)
        self.assertIn(f">{self.current.bed_no}<", content)
        self.assertIn(self.ended.start_date.strftime("%d-%m-%Y"), content)
        self.assertIn(self.ended.end_date.strftime("%d-%m-%Y"), content)
        self.assertIn("Current · Confirmed", content)
        self.assertLess(content.index("Current · Confirmed"), content.index("Room change approved"))
        self.assertNotContains(response, self.other_student.srn)
        self.assertNotContains(response, "Student checked out")
        self.assertEqual(len(response.context["allocations"]), 2)

    def test_fr55_student_history_is_fixed_to_authenticated_student(self):
        self.client.force_login(self.student_user)

        response = self.client.get(reverse("allocation:history"), {"student": self.other_student.pk})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Room change approved")
        self.assertNotContains(response, "Other Student")
        self.assertNotContains(response, "Student checked out")

    def test_fr55_student_without_allocations_gets_empty_state(self):
        empty_user = User.objects.create_user("emptyhistory@hms.local", PASSWORD, role=Role.STUDENT)
        self.make_student(empty_user, 23, "Empty History Student")
        self.client.force_login(empty_user)

        response = self.client.get(reverse("allocation:history"))

        self.assertContains(response, "You do not have any allocation history yet.")

    def test_fr55_warden_sees_allocation_history_within_hostel_scope(self):
        self.client.force_login(self.warden)

        response = self.client.get(reverse("allocation:history_manage"))

        self.assertContains(response, self.student.srn)
        self.assertContains(response, "Room change approved")
        self.assertNotContains(response, self.other_student.srn)
        self.assertNotContains(response, "Other History Block")
        self.assertNotContains(response, "Student checked out")

    def test_fr55_warden_search_remains_limited_to_authorized_hostels(self):
        self.client.force_login(self.warden)

        response = self.client.get(reverse("allocation:history_manage"), {"q": self.other_student.srn})

        self.assertContains(response, "No allocation history matched that student search")
        self.assertNotContains(response, "Other Student")
        self.assertNotContains(response, "Student checked out")

    def test_fr55_warden_cannot_access_history_outside_hostel_scope(self):
        self.client.force_login(self.warden)

        response = self.client.get(reverse("allocation:history_manage"), {"q": self.other_student.name})

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context["allocations"].object_list)

    def test_fr55_administrator_can_view_allocation_history_across_hostels(self):
        self.client.force_login(self.admin)

        response = self.client.get(reverse("allocation:history_manage"))

        self.assertContains(response, self.student.srn)
        self.assertContains(response, self.other_student.srn)
        self.assertContains(response, "Student checked out")

    def test_fr55_student_cannot_access_staff_history(self):
        self.client.force_login(self.student_user)

        response = self.client.get(reverse("allocation:history_manage"))

        self.assertEqual(response.status_code, 403)

    def test_fr55_ended_checkout_allocation_remains_available_to_student(self):
        self.client.force_login(self.other_user)

        response = self.client.get(reverse("allocation:history"))

        self.assertContains(response, "Student checked out")
        self.assertContains(response, self.out_of_scope.end_date.strftime("%d-%m-%Y"))
