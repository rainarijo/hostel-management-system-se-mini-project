from datetime import date

from django.core.exceptions import ValidationError
from django.test import TestCase

from apps.accounts.models import Role, User
from apps.allocation.models import Allocation, AllocationStatus
from apps.rooms.models import Hostel, Room, RoomStatus
from apps.rooms.validators import validate_allocation_room
from apps.students.models import StudentProfile


class RoomLifecycleTests(TestCase):
    def setUp(self):
        self.hostel = Hostel.objects.create(name="Lifecycle Hall", gender_type="M")
        self.first_room = Room.objects.create(hostel=self.hostel, room_no="101", floor=1, room_type="SINGLE",
                                              capacity=1, annual_fee=75000)
        self.second_room = Room.objects.create(hostel=self.hostel, room_no="102", floor=1, room_type="SINGLE",
                                               capacity=1, annual_fee=75000)
        self.students = []
        for number in range(1, 3):
            user = User.objects.create_user(f"lifecycle{number}@hms.local", "Strongpass2026", role=Role.STUDENT)
            self.students.append(StudentProfile.objects.create(
                user=user, srn=f"PES1UG24CS6{number:02d}", name=f"Lifecycle Student {number}",
                gender="M", program="B.Tech CSE", year=1))

    def create_allocation(self, student_index=0, room=None, status=AllocationStatus.PROVISIONAL):
        return Allocation.objects.create(
            student=self.students[student_index], room=room or self.first_room, bed_no=1,
            start_date=date.today(), status=status)

    def test_allocation_creation_status_transitions_and_room_moves_refresh_status(self):
        allocation = self.create_allocation()
        self.first_room.refresh_from_db()
        self.assertEqual(self.first_room.occupancy, 1)
        self.assertEqual(self.first_room.status, RoomStatus.FULL)

        allocation.status = AllocationStatus.ENDED
        allocation.save()
        self.first_room.refresh_from_db()
        self.assertEqual(self.first_room.occupancy, 0)
        self.assertEqual(self.first_room.status, RoomStatus.AVAILABLE)

        allocation.status = AllocationStatus.CONFIRMED
        allocation.save()
        allocation.room = self.second_room
        allocation.save()
        self.first_room.refresh_from_db()
        self.second_room.refresh_from_db()
        self.assertEqual(self.first_room.status, RoomStatus.AVAILABLE)
        self.assertEqual(self.second_room.status, RoomStatus.FULL)

    def test_maintenance_is_preserved_and_active_allocations_are_rejected(self):
        self.first_room.status = RoomStatus.MAINTENANCE
        self.first_room.save(update_fields=["status", "updated_at"])

        with self.assertRaisesMessage(ValidationError, "under maintenance"):
            self.create_allocation()

        allocation = self.create_allocation(status=AllocationStatus.ENDED)
        allocation.status = AllocationStatus.CONFIRMED
        with self.assertRaisesMessage(ValidationError, "under maintenance"):
            allocation.save()
        allocation.refresh_from_db()
        self.first_room.refresh_from_db()
        self.assertEqual(allocation.status, AllocationStatus.ENDED)
        self.assertEqual(self.first_room.status, RoomStatus.MAINTENANCE)

    def test_validator_excludes_the_allocation_being_updated(self):
        allocation = self.create_allocation()

        validate_allocation_room(
            self.first_room, allocation=allocation, status=AllocationStatus.CONFIRMED, bed_no=1)

        with self.assertRaisesMessage(ValidationError, "no vacant beds"):
            validate_allocation_room(self.first_room, status=AllocationStatus.PROVISIONAL, bed_no=1)
