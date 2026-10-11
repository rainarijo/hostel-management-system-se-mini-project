"""Tests for FR-4.6: no bed or student can have two active allocations (Test Plan TC-10)."""
from datetime import date

from django.db import IntegrityError, transaction
from django.test import TestCase

from apps.accounts.models import Role, User
from apps.allocation.models import Allocation, AllocationStatus
from apps.rooms.models import Hostel, Room, RoomStatus
from apps.students.models import StudentProfile


def make_student(n):
    user = User.objects.create_user(f"s{n}@hms.local", "Strongpass2026", role=Role.STUDENT)
    return StudentProfile.objects.create(user=user, srn=f"PES1UG24CS9{n:02d}", name=f"Student {n}",
                                         gender="M", program="B.Tech CSE", year=1)


class AllocationConstraintTests(TestCase):
    def setUp(self):
        hostel = Hostel.objects.create(name="Test Block", gender_type="M")
        self.room = Room.objects.create(hostel=hostel, room_no="101", floor=1, room_type="DOUBLE",
                                        capacity=2, annual_fee=75000)
        self.s1, self.s2 = make_student(1), make_student(2)

    def test_tc10_same_bed_cannot_be_allocated_twice(self):
        Allocation.objects.create(student=self.s1, room=self.room, bed_no=1, start_date=date.today())
        with self.assertRaises(IntegrityError), transaction.atomic():
            Allocation.objects.create(student=self.s2, room=self.room, bed_no=1, start_date=date.today())

    def test_tc10_student_cannot_hold_two_active_allocations(self):
        Allocation.objects.create(student=self.s1, room=self.room, bed_no=1, start_date=date.today())
        with self.assertRaises(IntegrityError), transaction.atomic():
            Allocation.objects.create(student=self.s1, room=self.room, bed_no=2, start_date=date.today())

    def test_ended_allocation_frees_the_bed(self):
        a = Allocation.objects.create(student=self.s1, room=self.room, bed_no=1, start_date=date.today())
        a.status = AllocationStatus.ENDED
        a.save()
        Allocation.objects.create(student=self.s2, room=self.room, bed_no=1, start_date=date.today())
        self.assertEqual(self.room.occupancy, 1)

    def test_room_status_becomes_full_at_capacity(self):
        Allocation.objects.create(student=self.s1, room=self.room, bed_no=1, start_date=date.today())
        Allocation.objects.create(student=self.s2, room=self.room, bed_no=2, start_date=date.today())
        self.room.refresh_status()
        self.assertEqual(self.room.status, RoomStatus.FULL)
