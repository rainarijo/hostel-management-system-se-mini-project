"""Tests for NFR-PERF-2: an allocation completes within 1 second for 95% of requests."""
import statistics
import time

from django.test import TestCase

from apps.accounts.models import Role, User
from apps.allocation.models import RoomApplication
from apps.allocation.services import allocate
from apps.rooms.models import Hostel, Room
from apps.students.models import StudentProfile

PASSWORD = "Strongpass2026"


class AllocationPerformanceTests(TestCase):
    def test_nfr_perf2_allocation_under_one_second(self):
        warden = User.objects.create_user("wb@hms.local", PASSWORD, role=Role.WARDEN)
        hostel = Hostel.objects.create(name="Cauvery Block", gender_type="M")
        hostel.wardens.add(warden)
        room = Room.objects.create(hostel=hostel, room_no="101", floor=1, room_type="DOUBLE", capacity=4,
                                   annual_fee=80000)
        rooms = [room] + [Room.objects.create(hostel=hostel, room_no=f"1{n:02d}", floor=1, room_type="DOUBLE",
                                              capacity=4, annual_fee=80000) for n in range(2, 6)]
        timings = []
        with self.assertLogs("hms.allocation", level="INFO") as logs:
            for n in range(20):
                user = User.objects.create_user(f"s{n}@hms.local", PASSWORD, role=Role.STUDENT)
                student = StudentProfile.objects.create(user=user, srn=f"PES1UG24CS{n:03d}", name=f"Student {n}",
                                                        gender="M", program="B.Tech CSE", year=1)
                application = RoomApplication.objects.create(student=student, academic_year="2026-2027",
                                                             preference_1="DOUBLE", application_no=f"APP-2026-{n:05d}")
                started = time.perf_counter()
                allocate(application, rooms[n // 4], n % 4 + 1, warden)
                timings.append(time.perf_counter() - started)

        p95 = statistics.quantiles(timings, n=20)[-1]          # 95th percentile
        self.assertLess(p95, 1.0, f"p95 {p95:.3f}s")
        records = [r for r in logs.records if r.getMessage() == "allocation created"]
        self.assertEqual(len(records), 20)
        self.assertIsInstance(records[0].allocation_ms, float)
        self.assertGreaterEqual(records[0].allocation_ms, 0)
        self.assertTrue(hasattr(records[0], "allocation_id"))
