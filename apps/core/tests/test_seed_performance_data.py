from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase
from django.db.models import Sum

from apps.accounts.models import Role, User
from apps.allocation.models import Allocation, ApplicationStatus, RoomApplication
from apps.complaints.models import Complaint
from apps.fees.models import FeeRecord
from apps.rooms.models import Hostel, Room
from apps.students.models import StudentProfile


class SeedPerformanceDataTests(TestCase):
    def setUp(self):
        User.objects.create_user("warden.boys@hms.local", "Strongpass2026", role=Role.WARDEN)

    def test_creates_a_repeatable_scale_shape_without_deleting_existing_data(self):
        call_command("seed_performance_data", students=10, beds=8, verbosity=0)

        self.assertEqual(StudentProfile.objects.filter(srn__startswith="LT").count(), 10)
        self.assertEqual(Room.objects.filter(hostel__name="HMS Load Test Hostel").aggregate(
            total=Sum("capacity"))["total"], 8)
        self.assertEqual(Allocation.objects.count(), 5)
        self.assertEqual(RoomApplication.objects.filter(status=ApplicationStatus.PENDING).count(), 5)
        self.assertEqual(FeeRecord.objects.count(), 5)
        self.assertEqual(Complaint.objects.count(), 5)

    def test_refuses_to_duplicate_or_overwrite_the_performance_hostel(self):
        Hostel.objects.create(name="HMS Load Test Hostel", gender_type="M")

        with self.assertRaises(CommandError):
            call_command("seed_performance_data", students=10, beds=8, verbosity=0)
