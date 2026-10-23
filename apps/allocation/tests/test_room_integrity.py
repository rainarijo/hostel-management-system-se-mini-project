from datetime import date

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import Role, User
from apps.allocation.models import Allocation, AllocationStatus
from apps.rooms.validators import validate_allocation_room
from apps.core.models import AuditLog
from apps.rooms.models import Hostel, Room, RoomStatus
from apps.students.models import StudentProfile


class RoomAllocationIntegrityTests(TestCase):
    def setUp(self):
        self.hostel = Hostel.objects.create(name="Integrity Block", gender_type="M")
        self.room = Room.objects.create(hostel=self.hostel, room_no="101", floor=1, room_type="DOUBLE",
                                        capacity=2, annual_fee=75000)
        self.students = []
        for number in range(1, 5):
            user = User.objects.create_user(f"integrity{number}@hms.local", "Strongpass2026", role=Role.STUDENT)
            self.students.append(StudentProfile.objects.create(
                user=user, srn=f"PES1UG24CS7{number:02d}", name=f"Integrity Student {number}",
                gender="M", program="B.Tech CSE", year=1))

    def make_allocation(self, student_no, bed_no, status=AllocationStatus.PROVISIONAL, room=None):
        return Allocation.objects.create(student=self.students[student_no - 1], room=room or self.room,
                                         bed_no=bed_no, start_date=date.today(), status=status)

    def test_provisional_and_confirmed_allocations_count_and_fill_room(self):
        self.make_allocation(1, 1, AllocationStatus.PROVISIONAL)
        self.assertEqual(self.room.occupancy, 1)
        self.assertEqual(self.room.status, RoomStatus.AVAILABLE)

        self.make_allocation(2, 2, AllocationStatus.CONFIRMED)
        self.room.refresh_from_db()
        self.assertEqual(self.room.occupancy, 2)
        self.assertEqual(self.room.status, RoomStatus.FULL)

    def test_ended_and_cancelled_allocations_are_not_occupied(self):
        self.make_allocation(1, 1, AllocationStatus.ENDED)
        self.make_allocation(2, 2, AllocationStatus.CANCELLED)

        self.room.refresh_from_db()
        self.assertEqual(self.room.occupancy, 0)
        self.assertEqual(self.room.status, RoomStatus.AVAILABLE)

    def test_ending_or_cancelling_active_allocation_releases_bed_and_updates_status(self):
        ended = self.make_allocation(1, 1)
        confirmed = self.make_allocation(2, 2, AllocationStatus.CONFIRMED)
        self.room.refresh_from_db()
        self.assertEqual(self.room.status, RoomStatus.FULL)

        ended.status = AllocationStatus.ENDED
        ended.save()
        self.room.refresh_from_db()
        self.assertEqual(self.room.occupancy, 1)
        self.assertEqual(self.room.status, RoomStatus.AVAILABLE)

        confirmed.status = AllocationStatus.CANCELLED
        confirmed.save()
        self.room.refresh_from_db()
        self.assertEqual(self.room.occupancy, 0)
        self.assertEqual(self.room.status, RoomStatus.AVAILABLE)

    def test_maintenance_status_is_preserved_when_occupancy_changes(self):
        allocation = self.make_allocation(1, 1)
        self.room.status = RoomStatus.MAINTENANCE
        self.room.save(update_fields=["status", "updated_at"])

        allocation.status = AllocationStatus.ENDED
        allocation.save()
        self.room.refresh_from_db()

        self.assertEqual(self.room.occupancy, 0)
        self.assertEqual(self.room.status, RoomStatus.MAINTENANCE)

    def test_moving_active_allocation_refreshes_both_rooms(self):
        first_room = Room.objects.create(hostel=self.hostel, room_no="102", floor=1, room_type="SINGLE",
                                         capacity=1, annual_fee=90000)
        second_room = Room.objects.create(hostel=self.hostel, room_no="103", floor=1, room_type="SINGLE",
                                          capacity=1, annual_fee=90000)
        allocation = self.make_allocation(1, 1, room=first_room)
        first_room.refresh_from_db()
        self.assertEqual(first_room.status, RoomStatus.FULL)

        allocation.room = second_room
        allocation.save()
        first_room.refresh_from_db()
        second_room.refresh_from_db()
        self.assertEqual(first_room.status, RoomStatus.AVAILABLE)
        self.assertEqual(second_room.status, RoomStatus.FULL)

    def test_valid_activation_updates_room_status(self):
        self.room.capacity = 1
        self.room.save(update_fields=["capacity", "updated_at"])
        allocation = self.make_allocation(1, 1, AllocationStatus.ENDED)

        allocation.status = AllocationStatus.CONFIRMED
        allocation.save()
        self.room.refresh_from_db()

        self.assertEqual(self.room.occupancy, 1)
        self.assertEqual(self.room.status, RoomStatus.FULL)

    def test_service_and_model_save_reject_unavailable_or_full_rooms(self):
        cases = (
            ("maintenance", lambda: setattr(self.room, "status", RoomStatus.MAINTENANCE)),
            ("inactive room", lambda: setattr(self.room, "is_active", False)),
            ("inactive hostel", lambda: setattr(self.hostel, "is_active", False)),
        )
        for label, set_unavailable in cases:
            with self.subTest(reason=label):
                set_unavailable()
                if label == "inactive hostel":
                    self.hostel.save(update_fields=["is_active", "updated_at"])
                else:
                    self.room.save(update_fields=["status", "is_active", "updated_at"])
                with self.assertRaises(ValidationError):
                    self.make_allocation(1, 1)
                self.assertEqual(Allocation.objects.count(), 0)
                self.room.refresh_from_db()
                self.room.is_active = True
                self.room.status = RoomStatus.AVAILABLE
                self.room.save(update_fields=["is_active", "status", "updated_at"])
                self.hostel.is_active = True
                self.hostel.save(update_fields=["is_active", "updated_at"])

        self.make_allocation(1, 1)
        self.make_allocation(2, 2)
        with self.assertRaises(ValidationError):
            validate_allocation_room(self.room, status=AllocationStatus.PROVISIONAL)

    def test_model_save_rejects_allocation_that_exceeds_capacity(self):
        self.room.capacity = 1
        self.room.save(update_fields=["capacity", "updated_at"])
        self.make_allocation(1, 1)

        with self.assertRaises(ValidationError):
            self.make_allocation(2, 2)

        self.assertEqual(Allocation.objects.count(), 1)
        self.room.refresh_from_db()
        self.assertEqual(self.room.status, RoomStatus.FULL)

    def test_model_save_rejects_bed_number_outside_room_capacity(self):
        with self.assertRaises(ValidationError):
            self.make_allocation(1, 3)

        self.assertEqual(Allocation.objects.count(), 0)
        self.room.refresh_from_db()
        self.assertEqual(self.room.status, RoomStatus.AVAILABLE)

    def test_model_save_rejects_activation_that_exceeds_capacity(self):
        self.room.capacity = 1
        self.room.save(update_fields=["capacity", "updated_at"])
        self.make_allocation(1, 1)
        historical = self.make_allocation(2, 2, AllocationStatus.ENDED)
        historical.status = AllocationStatus.CONFIRMED

        with self.assertRaises(ValidationError):
            historical.save()

        historical.refresh_from_db()
        self.assertEqual(historical.status, AllocationStatus.ENDED)
        self.assertEqual(self.room.occupancy, 1)

    def test_activation_is_rejected_for_inactive_room_or_hostel(self):
        allocation = self.make_allocation(1, 1, AllocationStatus.ENDED)

        self.room.is_active = False
        self.room.save(update_fields=["is_active", "updated_at"])
        allocation.status = AllocationStatus.CONFIRMED
        with self.assertRaises(ValidationError):
            allocation.save()
        allocation.refresh_from_db()
        self.assertEqual(allocation.status, AllocationStatus.ENDED)

        self.room.is_active = True
        self.room.save(update_fields=["is_active", "updated_at"])
        self.hostel.is_active = False
        self.hostel.save(update_fields=["is_active", "updated_at"])
        allocation.status = AllocationStatus.CONFIRMED
        with self.assertRaises(ValidationError):
            allocation.save()
        allocation.refresh_from_db()
        self.assertEqual(allocation.status, AllocationStatus.ENDED)

    def test_activation_failure_does_not_persist_status_or_change_occupancy(self):
        self.room.status = RoomStatus.MAINTENANCE
        self.room.save(update_fields=["status", "updated_at"])
        allocation = self.make_allocation(1, 1, AllocationStatus.ENDED)
        allocation.status = AllocationStatus.CONFIRMED

        with self.assertRaises(ValidationError):
            allocation.save()

        allocation.refresh_from_db()
        self.room.refresh_from_db()
        self.assertEqual(allocation.status, AllocationStatus.ENDED)
        self.assertEqual(self.room.occupancy, 0)
        self.assertEqual(self.room.status, RoomStatus.MAINTENANCE)

    def test_admin_rejects_allocation_creation_for_maintenance_room(self):
        admin = User.objects.create_superuser("admin-integrity@hms.local", "Strongpass2026")
        self.client.force_login(admin)
        self.room.status = RoomStatus.MAINTENANCE
        self.room.save(update_fields=["status", "updated_at"])

        response = self.client.post(reverse("admin:allocation_allocation_add"), {
            "student": self.students[0].pk, "room": self.room.pk, "bed_no": 1, "academic_year": "",
            "application": "", "start_date": date.today().isoformat(), "end_date": "",
            "status": AllocationStatus.PROVISIONAL, "end_reason": "",
        })

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "under maintenance")
        self.assertEqual(Allocation.objects.count(), 0)
        self.assertFalse(AuditLog.objects.filter(action="ALLOCATION_CREATED").exists())

    def test_admin_rejects_allocation_for_inactive_or_full_rooms(self):
        admin = User.objects.create_superuser("admin-unavailable@hms.local", "Strongpass2026")
        self.client.force_login(admin)
        url = reverse("admin:allocation_allocation_add")

        self.room.is_active = False
        self.room.save(update_fields=["is_active", "updated_at"])
        inactive_room_response = self.client.post(url, {
            "student": self.students[0].pk, "room": self.room.pk, "bed_no": 1, "academic_year": "",
            "application": "", "start_date": date.today().isoformat(), "end_date": "",
            "status": AllocationStatus.PROVISIONAL, "end_reason": "",
        })
        self.assertEqual(inactive_room_response.status_code, 200)
        self.assertContains(inactive_room_response, "inactive room")
        self.assertEqual(Allocation.objects.count(), 0)

        self.room.is_active = True
        self.room.save(update_fields=["is_active", "updated_at"])
        self.hostel.is_active = False
        self.hostel.save(update_fields=["is_active", "updated_at"])
        inactive_hostel_response = self.client.post(url, {
            "student": self.students[0].pk, "room": self.room.pk, "bed_no": 1, "academic_year": "",
            "application": "", "start_date": date.today().isoformat(), "end_date": "",
            "status": AllocationStatus.PROVISIONAL, "end_reason": "",
        })
        self.assertEqual(inactive_hostel_response.status_code, 200)
        self.assertContains(inactive_hostel_response, "inactive hostel")
        self.assertEqual(Allocation.objects.count(), 0)

        self.hostel.is_active = True
        self.hostel.save(update_fields=["is_active", "updated_at"])
        self.make_allocation(1, 1)
        self.make_allocation(2, 2)
        full_room_response = self.client.post(url, {
            "student": self.students[2].pk, "room": self.room.pk, "bed_no": 1, "academic_year": "",
            "application": "", "start_date": date.today().isoformat(), "end_date": "",
            "status": AllocationStatus.PROVISIONAL, "end_reason": "",
        })
        self.assertEqual(full_room_response.status_code, 200)
        self.assertContains(full_room_response, "no vacant beds")
        self.assertEqual(Allocation.objects.count(), 2)

    def test_admin_rejects_bed_number_outside_room_capacity(self):
        admin = User.objects.create_superuser("admin-bed@hms.local", "Strongpass2026")
        self.client.force_login(admin)
        response = self.client.post(reverse("admin:allocation_allocation_add"), {
            "student": self.students[0].pk, "room": self.room.pk, "bed_no": 3, "academic_year": "",
            "application": "", "start_date": date.today().isoformat(), "end_date": "",
            "status": AllocationStatus.PROVISIONAL, "end_reason": "",
        })

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "within the room")
        self.assertEqual(Allocation.objects.count(), 0)
        self.assertFalse(AuditLog.objects.filter(action="ALLOCATION_CREATED").exists())

    def test_admin_allows_valid_creation_and_disables_hard_delete(self):
        admin = User.objects.create_superuser("admin-valid@hms.local", "Strongpass2026")
        self.client.force_login(admin)
        response = self.client.post(reverse("admin:allocation_allocation_add"), {
            "student": self.students[0].pk, "room": self.room.pk, "bed_no": 1, "academic_year": "",
            "application": "", "start_date": date.today().isoformat(), "end_date": "",
            "status": AllocationStatus.PROVISIONAL, "end_reason": "",
        })

        self.assertEqual(response.status_code, 302)
        allocation = Allocation.objects.get()
        self.room.refresh_from_db()
        self.assertEqual(self.room.occupancy, 1)
        self.assertEqual(self.room.status, RoomStatus.AVAILABLE)
        self.assertTrue(AuditLog.objects.filter(action="ALLOCATION_CREATED", entity_id=str(allocation.pk)).exists())
        delete_url = reverse("admin:allocation_allocation_delete", args=[allocation.pk])
        self.assertEqual(self.client.get(delete_url).status_code, 403)
