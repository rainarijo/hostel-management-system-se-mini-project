"""Create a synthetic data set for isolated performance and load testing."""
from datetime import date
from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.accounts.models import Role, User
from apps.allocation.models import Allocation, AllocationStatus, ApplicationStatus, RoomApplication
from apps.complaints.models import Complaint, ComplaintCategory
from apps.fees.models import FeeRecord
from apps.rooms.models import Hostel, Room, RoomStatus, RoomType
from apps.students.models import StudentProfile

HOSTEL_NAME = "HMS Load Test Hostel"
ACADEMIC_YEAR = "2026-2027"


class Command(BaseCommand):
    help = "Create synthetic student, room, allocation, fee, complaint and application data for load tests."

    def add_arguments(self, parser):
        parser.add_argument("--students", type=int, default=5000, help="Number of synthetic students to create.")
        parser.add_argument("--beds", type=int, default=4000, help="Number of synthetic beds to create.")

    @transaction.atomic
    def handle(self, *args, **options):
        student_count = options["students"]
        bed_count = options["beds"]
        if student_count < 1 or bed_count < 1:
            raise CommandError("--students and --beds must both be positive.")
        if Hostel.objects.filter(name=HOSTEL_NAME).exists():
            raise CommandError(f"{HOSTEL_NAME} already exists; use a clean, dedicated load-test database.")

        try:
            warden = User.objects.get(email="warden.boys@hms.local", role=Role.WARDEN, is_active=True)
        except User.DoesNotExist as exc:
            raise CommandError("Run `python manage.py seed_data` first to create the load-test warden.") from exc

        hostel = Hostel.objects.create(name=HOSTEL_NAME, gender_type="M")
        hostel.wardens.add(warden)

        rooms = []
        remaining_beds = bed_count
        while remaining_beds:
            capacity = min(3, remaining_beds)
            room_type = {1: RoomType.SINGLE, 2: RoomType.DOUBLE, 3: RoomType.TRIPLE}[capacity]
            room_number = len(rooms) + 1
            rooms.append(Room(
                hostel=hostel,
                room_no=f"L{room_number:05d}",
                floor=((room_number - 1) // 70) % 20 + 1,
                room_type=room_type,
                capacity=capacity,
                annual_fee=Decimal("75000.00"),
            ))
            remaining_beds -= capacity
        Room.objects.bulk_create(rooms, batch_size=500)

        users = User.objects.bulk_create([
            User(
                email=f"perf-student-{number:05d}@loadtest.hms.local",
                password="!",
                role=Role.STUDENT,
                first_name=f"Load Test {number:05d}",
                is_active=False,
            )
            for number in range(1, student_count + 1)
        ], batch_size=500)
        profiles = StudentProfile.objects.bulk_create([
            StudentProfile(
                user=user,
                srn=f"LT{number:011d}",
                name=f"Load Test Student {number:05d}",
                gender="M",
                program="B.Tech CSE",
                year=(number - 1) % 4 + 1,
            )
            for number, user in enumerate(users, start=1)
        ], batch_size=500)

        bed_slots = [
            (room, bed_no)
            for room in rooms
            for bed_no in range(1, room.capacity + 1)
        ]
        allocated_count = min(student_count // 2, bed_count)
        allocations = [
            Allocation(
                student=profiles[number],
                room=room,
                bed_no=bed_no,
                academic_year=ACADEMIC_YEAR,
                start_date=date.today(),
                status=AllocationStatus.CONFIRMED,
            )
            for number, (room, bed_no) in enumerate(bed_slots[:allocated_count])
        ]
        Allocation.objects.bulk_create(allocations, batch_size=500)
        FeeRecord.objects.bulk_create([
            FeeRecord(
                allocation=allocation,
                academic_year=ACADEMIC_YEAR,
                total_amount=allocation.room.annual_fee,
            )
            for allocation in allocations
        ], batch_size=500)

        occupied_by_room = {}
        for room, _ in bed_slots[:allocated_count]:
            occupied_by_room[room.pk] = occupied_by_room.get(room.pk, 0) + 1
        for room in rooms:
            if occupied_by_room.get(room.pk, 0) == room.capacity:
                room.status = RoomStatus.FULL
        Room.objects.bulk_update(rooms, ["status"], batch_size=500)

        pending_profiles = profiles[allocated_count:]
        applications = [
            RoomApplication(
                student=profile,
                academic_year=ACADEMIC_YEAR,
                preference_1=RoomType.TRIPLE,
                preference_2=RoomType.DOUBLE,
                preference_3=RoomType.SINGLE,
                application_no=f"PERF-{number:010d}",
                status=ApplicationStatus.PENDING,
            )
            for number, profile in enumerate(pending_profiles, start=1)
        ]
        RoomApplication.objects.bulk_create(applications, batch_size=500)

        complaints = [
            Complaint(
                complaint_no=f"CMP-2026-{number:05d}",
                student=allocation.student,
                room=allocation.room,
                category=ComplaintCategory.OTHER,
                description="Synthetic load-test complaint.",
            )
            for number, allocation in enumerate(allocations[:min(allocated_count, 500)], start=1)
        ]
        Complaint.objects.bulk_create(complaints, batch_size=500)

        self.stdout.write(self.style.SUCCESS(
            f"Created {student_count} synthetic students, {bed_count} beds, {allocated_count} allocations, "
            f"{len(applications)} pending applications, and {len(complaints)} complaints in {HOSTEL_NAME}."
        ))
