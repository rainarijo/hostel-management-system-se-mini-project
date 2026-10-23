"""Tests for FR-4.5, FR-4.6: allocate a bed (Test Plan TC-09, TC-10)."""
from datetime import date
from unittest import mock

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import Role, User
from apps.allocation.models import Allocation, AllocationStatus, ApplicationStatus, RoomApplication
from apps.allocation.services import allocate, candidate_beds
from apps.allocation.signals import allocation_created
from apps.core.exceptions import (AlreadyAllocated, BedUnavailable, GenderMismatch, RoomUnderMaintenance,
                                  ValidationFailure)
from apps.core.models import AuditLog
from apps.rooms.models import Hostel, Room, RoomStatus
from apps.students.models import StudentProfile

PASSWORD = "Strongpass2026"


def next_31_may():
    today = timezone.localdate()
    end = date(today.year, 5, 31)
    return end if today <= end else date(today.year + 1, 5, 31)


class AllocateTests(TestCase):
    def setUp(self):
        self.n = 0
        self.warden = User.objects.create_user("wb@hms.local", PASSWORD, role=Role.WARDEN)
        self.boys = Hostel.objects.create(name="Cauvery Block", gender_type="M")
        self.boys.wardens.add(self.warden)
        self.girls = Hostel.objects.create(name="Kaveri Block", gender_type="F")
        self.single = self.make_room(self.boys, "101", "SINGLE", 1)
        self.double = self.make_room(self.boys, "102", "DOUBLE", 2)
        self.application = self.make_application()

    def make_room(self, hostel, room_no, room_type, capacity, **extra):
        return Room.objects.create(hostel=hostel, room_no=room_no, floor=1, room_type=room_type, capacity=capacity,
                                   annual_fee=80000, **extra)

    def make_application(self, gender="M", pref="SINGLE"):
        self.n += 1
        user = User.objects.create_user(f"s{self.n}@hms.local", PASSWORD, role=Role.STUDENT)
        student = StudentProfile.objects.create(user=user, srn=f"PES1UG24CS{self.n:03d}", name=f"Student {self.n}",
                                                gender=gender, program="B.Tech CSE", year=1)
        return RoomApplication.objects.create(student=student, academic_year="2026-2027", preference_1=pref,
                                              application_no=f"APP-2026-{self.n:05d}")

    def assert_untouched(self, application=None):
        application = application or self.application
        application.refresh_from_db()
        self.assertEqual(application.status, ApplicationStatus.PENDING)
        self.assertFalse(Allocation.objects.filter(application=application).exists())

    def test_tc09_warden_allocates_vacant_bed(self):
        receiver = mock.Mock()
        allocation_created.connect(receiver)
        self.addCleanup(allocation_created.disconnect, receiver)

        allocation = allocate(self.application, self.single, 1, self.warden)

        self.assertEqual(allocation.status, AllocationStatus.PROVISIONAL)
        self.assertEqual(allocation.end_date, next_31_may())
        self.assertEqual(allocation.academic_year, "2026-2027")
        self.application.refresh_from_db()
        self.assertEqual(self.application.status, ApplicationStatus.ALLOCATED)
        receiver.assert_called_once()
        self.assertEqual(receiver.call_args.kwargs["allocation"], allocation)
        self.single.refresh_from_db()
        self.assertEqual(self.single.status, RoomStatus.FULL)
        self.assertTrue(AuditLog.objects.filter(action="ALLOCATE", entity_id=str(allocation.pk)).exists())

    def test_tc09_gender_mismatch_rejected(self):
        girls_room = self.make_room(self.girls, "201", "SINGLE", 1)
        admin = User.objects.create_user("admin@hms.local", PASSWORD, role=Role.ADMIN)
        with self.assertRaises(GenderMismatch):
            allocate(self.application, girls_room, 1, admin)
        self.assert_untouched()

    def test_tc09_maintenance_room_rejected(self):
        room = self.make_room(self.boys, "103", "SINGLE", 1, status=RoomStatus.MAINTENANCE)
        with self.assertRaises(RoomUnderMaintenance):
            allocate(self.application, room, 1, self.warden)
        self.assert_untouched()

    def test_tc09_already_allocated_student_rejected(self):
        Allocation.objects.create(student=self.application.student, room=self.double, bed_no=1,
                                  start_date=timezone.localdate())
        with self.assertRaises(AlreadyAllocated):
            allocate(self.application, self.single, 1, self.warden)
        self.assert_untouched()

    def test_tc09_bed_number_outside_capacity_rejected(self):
        for bed_no in (0, 3):
            with self.assertRaises(ValidationFailure):
                allocate(self.application, self.double, bed_no, self.warden)
        self.assert_untouched()

    def test_tc10_second_allocation_of_same_bed_raises_bed_unavailable(self):
        allocate(self.application, self.double, 2, self.warden)
        second = self.make_application()
        with self.assertRaisesMessage(BedUnavailable, "Bed no longer available."):
            allocate(second, self.double, 2, self.warden)
        self.assert_untouched(second)

    def test_tc10_constraint_still_protects_when_precheck_fails(self):
        allocate(self.application, self.double, 1, self.warden)
        second = self.make_application()
        # Simulates two Wardens passing the pre-check at the same moment: only uniq_active_bed stops the second.
        with mock.patch("apps.allocation.services._bed_is_held", return_value=False):
            with self.assertRaises(BedUnavailable):
                allocate(second, self.double, 1, self.warden)
        self.assert_untouched(second)
        self.assertEqual(Allocation.objects.active().filter(room=self.double, bed_no=1).count(), 1)

    def test_tc09_failing_signal_receiver_rolls_back(self):
        def broken(**kwargs):
            raise RuntimeError("fee service down")
        allocation_created.connect(broken)
        self.addCleanup(allocation_created.disconnect, broken)
        with self.assertRaises(RuntimeError):
            allocate(self.application, self.single, 1, self.warden)
        self.assert_untouched()
        self.single.refresh_from_db()
        self.assertEqual(self.single.status, RoomStatus.AVAILABLE)

    def test_tc09_candidate_beds_exclude_held_maintenance_and_other_gender(self):
        Allocation.objects.create(student=self.make_application().student, room=self.double, bed_no=1,
                                  start_date=timezone.localdate())
        self.make_room(self.boys, "103", "SINGLE", 1, status=RoomStatus.MAINTENANCE)
        self.make_room(self.girls, "201", "SINGLE", 1)
        beds = [(room.room_no, bed_no) for room, bed_no in candidate_beds(self.application, self.warden)]
        self.assertEqual(beds, [("101", 1), ("102", 2)])

    def test_tc09_candidate_beds_put_preferred_room_type_first(self):
        application = self.make_application(pref="DOUBLE")
        beds = [(room.room_no, bed_no) for room, bed_no in candidate_beds(application, self.warden)]
        self.assertEqual(beds, [("102", 1), ("102", 2), ("101", 1)])

    def test_tc09_warden_outside_scope_gets_404(self):
        girls_warden = User.objects.create_user("wg@hms.local", PASSWORD, role=Role.WARDEN)
        self.girls.wardens.add(girls_warden)
        self.client.login(email="wg@hms.local", password=PASSWORD)
        url = reverse("allocation:allocate", args=[self.application.pk])
        self.assertEqual(self.client.get(url).status_code, 404)
        self.assertEqual(self.client.post(url, {"bed": f"{self.single.pk}:1"}).status_code, 404)
        self.assert_untouched()

    def test_tc09_warden_cannot_allocate_room_in_other_wardens_hostel(self):
        other_boys = Hostel.objects.create(name="Tunga Block", gender_type="M")
        room = self.make_room(other_boys, "301", "SINGLE", 1)
        self.client.login(email="wb@hms.local", password=PASSWORD)
        resp = self.client.post(reverse("allocation:allocate", args=[self.application.pk]), {"bed": f"{room.pk}:1"})
        self.assertEqual(resp.status_code, 404)
        self.assert_untouched()

    def test_tc09_student_gets_403(self):
        self.client.login(email=self.application.student.user.email, password=PASSWORD)
        self.assertEqual(self.client.get(reverse("allocation:allocate", args=[self.application.pk])).status_code, 403)

    def test_tc09_view_success_redirects_to_queue(self):
        self.client.login(email="wb@hms.local", password=PASSWORD)
        url = reverse("allocation:allocate", args=[self.application.pk])
        page = self.client.get(url)
        self.assertContains(page, "Cauvery Block - Room 101 (Single) - Bed 1 - preference 1")
        resp = self.client.post(url, {"bed": f"{self.single.pk}:1"}, follow=True)
        self.assertRedirects(resp, reverse("allocation:queue"))
        self.assertContains(resp, "(Provisional)")
        self.assertTrue(Allocation.objects.filter(application=self.application, bed_no=1).exists())

    def test_tc10_view_shows_bed_no_longer_available_with_409(self):
        self.client.login(email="wb@hms.local", password=PASSWORD)
        url = reverse("allocation:allocate", args=[self.application.pk])
        self.client.get(url)                                  # Warden opens the page; the bed is still free
        other = self.make_application()
        allocate(other, self.double, 2, self.warden)          # another Warden takes it first
        resp = self.client.post(url, {"bed": f"{self.double.pk}:2"})
        self.assertContains(resp, "Bed no longer available.", status_code=409)
        self.assert_untouched()
