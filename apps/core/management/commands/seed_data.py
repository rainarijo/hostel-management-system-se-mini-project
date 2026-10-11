"""Load sample data for development: python manage.py seed_data

Creates an administrator, two wardens, two hostels with rooms, a master list,
and six students (two with allocations). All accounts share the password below.
"""
from datetime import date, timedelta

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.accounts.models import Role, User
from apps.allocation.models import Allocation, ApplicationWindow
from apps.fees.models import FeeRecord
from apps.notifications.models import Announcement
from apps.rooms.models import Hostel, Room, RoomType
from apps.students.models import MasterStudent, StudentProfile

PASSWORD = "Hostel2026pass"

STUDENTS = [
    ("PES1UG24CS101", "Aarav Menon", "M", 1), ("PES1UG24CS102", "Kabir Rao", "M", 2),
    ("PES1UG24CS103", "Rohan Iyer", "M", 3), ("PES1UG24CS104", "Ananya Shetty", "F", 1),
    ("PES1UG24CS105", "Diya Nair", "F", 2), ("PES1UG24CS106", "Meera Pillai", "F", 3),
]


class Command(BaseCommand):
    help = "Load sample data for development and demos."

    def add_arguments(self, parser):
        parser.add_argument("--reset", action="store_true", help="Delete existing sample data first.")

    @transaction.atomic
    def handle(self, *args, **opts):
        if User.objects.filter(email="admin@hms.local").exists() and not opts["reset"]:
            self.stdout.write(self.style.WARNING("Sample data already loaded. Use --reset to reload."))
            return
        if opts["reset"]:
            for model in (FeeRecord, Allocation, Announcement, ApplicationWindow, Room, Hostel,
                          StudentProfile, MasterStudent):
                model.objects.all().delete()
            User.objects.filter(email__endswith="@hms.local").delete()

        admin = User.objects.create_superuser("admin@hms.local", PASSWORD, first_name="Hostel", last_name="Office")
        w1 = User.objects.create_user("warden.boys@hms.local", PASSWORD, role=Role.WARDEN,
                                      first_name="Suresh", last_name="Kumar")
        w2 = User.objects.create_user("warden.girls@hms.local", PASSWORD, role=Role.WARDEN,
                                      first_name="Lakshmi", last_name="Rao")

        boys = Hostel.objects.create(name="Cauvery Block", gender_type="M")
        girls = Hostel.objects.create(name="Kabini Block", gender_type="F")
        boys.wardens.add(w1)
        girls.wardens.add(w2)

        layout = [(RoomType.SINGLE, 1, 95000), (RoomType.DOUBLE, 2, 75000), (RoomType.TRIPLE, 3, 60000)]
        for hostel in (boys, girls):
            for floor in (1, 2):
                for i, (rtype, cap, fee) in enumerate(layout, start=1):
                    Room.objects.create(hostel=hostel, room_no=f"{floor}0{i}", floor=floor,
                                        room_type=rtype, capacity=cap, annual_fee=fee)

        today = date.today()
        year = today.year if today.month >= 6 else today.year - 1
        ApplicationWindow.objects.create(academic_year=f"{year}-{year + 1}", start_date=today,
                                         end_date=today + timedelta(days=30))

        for idx, (srn, name, gender, yr) in enumerate(STUDENTS, start=1):
            email = f"student{idx}@hms.local"
            MasterStudent.objects.create(srn=srn, name=name, gender=gender, program="B.Tech CSE", year=yr, email=email)
            first, last = name.split(" ", 1)
            user = User.objects.create_user(email, PASSWORD, role=Role.STUDENT, first_name=first, last_name=last)
            StudentProfile.objects.create(
                user=user, srn=srn, name=name, gender=gender, program="B.Tech CSE", year=yr,
                mobile=f"98450000{idx:02d}", permanent_address="12, 4th Cross, Jayanagar, Bengaluru",
                guardian_name=f"Parent of {first}", guardian_relationship="Parent",
                guardian_mobile=f"98860000{idx:02d}", blood_group="O+",
            )

        for srn, room in (("PES1UG24CS102", Room.objects.get(hostel=boys, room_no="102")),
                          ("PES1UG24CS105", Room.objects.get(hostel=girls, room_no="103"))):
            alloc = Allocation.objects.create(student=StudentProfile.objects.get(srn=srn), room=room,
                                              bed_no=1, start_date=today)
            FeeRecord.objects.create(allocation=alloc, total_amount=room.annual_fee)
            room.refresh_status()

        Announcement.objects.create(hostel=boys, title="Water supply maintenance",
                                    body="Water will be off on Saturday from 10:00 to 13:00.",
                                    expiry_date=today + timedelta(days=7), created_by=w1)

        self.stdout.write(self.style.SUCCESS("Sample data loaded. Log in with any of these (password: %s):" % PASSWORD))
        for email in ("admin@hms.local", "warden.boys@hms.local", "warden.girls@hms.local",
                      "student1@hms.local ... student6@hms.local"):
            self.stdout.write(f"  {email}")
        _ = admin
