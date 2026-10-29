from datetime import date

from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import Role, User
from apps.allocation.models import Allocation, AllocationStatus
from apps.rooms.models import Hostel, Room, RoomType
from apps.students.models import StudentProfile


class ActiveAllocationListScalabilityTests(TestCase):
    def test_active_allocation_list_is_paginated(self):
        warden = User.objects.create_user("scale-warden@hms.local", "Strongpass2026", role=Role.WARDEN)
        hostel = Hostel.objects.create(name="Scale Allocation Hostel", gender_type="M")
        hostel.wardens.add(warden)
        users = User.objects.bulk_create([
            User(email=f"allocation-student-{number}@hms.local", password="!", role=Role.STUDENT)
            for number in range(1, 52)
        ])
        students = StudentProfile.objects.bulk_create([
            StudentProfile(
                user=user,
                srn=f"AL{number:011d}",
                name=f"Allocation Student {number}",
                gender="M",
                program="B.Tech CSE",
                year=2,
            )
            for number, user in enumerate(users, start=1)
        ])
        rooms = Room.objects.bulk_create([
            Room(
                hostel=hostel,
                room_no=f"A{number:03d}",
                floor=1,
                room_type=RoomType.SINGLE,
                capacity=1,
                annual_fee=75000,
            )
            for number in range(1, 52)
        ])
        Allocation.objects.bulk_create([
            Allocation(
                student=student,
                room=room,
                bed_no=1,
                start_date=date(2026, 6, 1),
                status=AllocationStatus.CONFIRMED,
            )
            for student, room in zip(students, rooms)
        ])
        self.client.force_login(warden)

        first_page = self.client.get(reverse("allocation:active_allocations"))
        self.assertEqual(len(first_page.context["allocations"]), 50)
        self.assertContains(first_page, "Page 1 of 2")

        second_page = self.client.get(reverse("allocation:active_allocations"), {"page": 2})
        self.assertEqual(len(second_page.context["allocations"]), 1)
