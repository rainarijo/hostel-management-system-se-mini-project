"""Tests for FR-4.2, FR-4.3: apply for a room (Test Plan TC-08)."""
from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import Role, User
from apps.allocation.models import Allocation, ApplicationWindow, RoomApplication
from apps.allocation.services import vacancy_by_room_type
from apps.core.models import AuditLog
from apps.rooms.models import Hostel, Room, RoomStatus
from apps.students.models import MasterStudent, StudentProfile

PASSWORD = "Strongpass2026"
COMPLETE = {"mobile": "9876543210", "permanent_address": "12 MG Road, Bengaluru", "guardian_name": "R Kumar",
            "guardian_relationship": "Father", "guardian_mobile": "9876501234", "blood_group": "O+"}


def make_student(n, gender="M", complete=True):
    user = User.objects.create_user(f"s{n}@hms.local", PASSWORD, role=Role.STUDENT)
    return StudentProfile.objects.create(user=user, srn=f"PES1UG24CS9{n:02d}", name=f"Student {n}", gender=gender,
                                         program="B.Tech CSE", year=1, **(COMPLETE if complete else {}))


class ApplyForRoomTests(TestCase):
    def setUp(self):
        today = timezone.localdate()
        self.window = ApplicationWindow.objects.create(academic_year="2026-2027", start_date=today - timedelta(days=5),
                                                       end_date=today + timedelta(days=5))
        self.student = make_student(1)
        MasterStudent.objects.create(srn="PES1UG24CS902", name="Student 2", gender="M", program="B.Tech CSE",
                                     year=1, email="s2@university.edu")
        self.url = reverse("allocation:apply")

    def apply(self, student=None, **data):
        self.client.login(email=(student or self.student).user.email, password=PASSWORD)
        payload = {"preference_1": "DOUBLE", "preference_2": "TRIPLE", "preference_3": "",
                   "preferred_roommate_srn": ""}
        payload.update(data)
        return self.client.post(self.url, payload)

    def test_tc08_complete_profile_can_apply_and_gets_number(self):
        resp = self.apply(preferred_roommate_srn="pes1ug24cs902")
        application = RoomApplication.objects.get(student=self.student)
        self.assertEqual(application.application_no, f"APP-{timezone.now().year}-00001")
        self.assertRedirects(resp, reverse("allocation:application_detail", args=[application.application_no]))
        self.assertEqual((application.preference_1, application.preference_2, application.preference_3),
                         ("DOUBLE", "TRIPLE", ""))
        self.assertEqual(application.preferred_roommate_srn, "PES1UG24CS902")
        self.assertEqual(application.academic_year, "2026-2027")
        self.assertTrue(AuditLog.objects.filter(action="APPLICATION_SUBMITTED").exists())
        page = self.client.get(resp["Location"])
        self.assertContains(page, application.application_no)
        self.assertContains(page, timezone.localdate().strftime("%d-%m-%Y"))

    def test_tc08_second_application_rejected(self):
        self.apply()
        resp = self.apply(preference_1="SINGLE", preference_2="")
        self.assertEqual(resp.status_code, 409)
        self.assertContains(resp, "You have already applied for this academic year.", status_code=409)
        self.assertEqual(RoomApplication.objects.count(), 1)

    def test_tc08_application_outside_window_rejected(self):
        self.window.end_date = timezone.localdate() - timedelta(days=1)
        self.window.save()
        self.client.login(email=self.student.user.email, password=PASSWORD)
        self.assertContains(self.client.get(self.url), "Applications are closed")
        resp = self.apply()
        self.assertContains(resp, "The application window is closed.", status_code=409)
        self.assertFalse(RoomApplication.objects.exists())

    def test_tc08_incomplete_profile_rejected(self):
        student = make_student(3, complete=False)
        resp = self.apply(student=student)
        self.assertContains(resp, "Complete your profile before applying.", status_code=409)
        self.assertFalse(RoomApplication.objects.exists())

    def test_tc08_duplicate_preferences_rejected(self):
        resp = self.apply(preference_2="DOUBLE")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("preference_2", resp.context["form"].errors)
        resp = self.apply(preference_2="", preference_3="SINGLE")
        self.assertIn("preference_2", resp.context["form"].errors)
        self.assertFalse(RoomApplication.objects.exists())

    def test_tc08_unknown_or_own_roommate_srn_rejected(self):
        for srn in ("PES1UG24CS999", self.student.srn):
            resp = self.apply(preferred_roommate_srn=srn)
            self.assertEqual(resp.status_code, 200)
            self.assertIn("preferred_roommate_srn", resp.context["form"].errors, srn)
        self.assertFalse(RoomApplication.objects.exists())

    def test_tc08_vacancy_counts_gender_matching_and_skip_maintenance(self):
        boys = Hostel.objects.create(name="Boys Block", gender_type="M")
        girls = Hostel.objects.create(name="Girls Block", gender_type="F")
        closed = Hostel.objects.create(name="Old Block", gender_type="M", is_active=False)
        double = Room.objects.create(hostel=boys, room_no="101", floor=1, room_type="DOUBLE", capacity=2,
                                     annual_fee=75000)
        Room.objects.create(hostel=boys, room_no="102", floor=1, room_type="SINGLE", capacity=1, annual_fee=90000,
                            status=RoomStatus.MAINTENANCE)
        Room.objects.create(hostel=boys, room_no="103", floor=1, room_type="TRIPLE", capacity=3, annual_fee=60000)
        Room.objects.create(hostel=girls, room_no="201", floor=2, room_type="SINGLE", capacity=1, annual_fee=90000)
        Room.objects.create(hostel=closed, room_no="301", floor=3, room_type="SINGLE", capacity=1, annual_fee=90000)
        Allocation.objects.create(student=make_student(4), room=double, bed_no=1, start_date=timezone.localdate())
        self.assertEqual(vacancy_by_room_type(self.student), {"SINGLE": 0, "DOUBLE": 1, "TRIPLE": 3})

        self.client.login(email=self.student.user.email, password=PASSWORD)
        page = self.client.get(self.url)
        self.assertContains(page, "Double (1 vacant bed)")
        self.assertNotContains(page, "101")

    def test_tc08_warden_and_admin_get_403(self):
        for role in (Role.WARDEN, Role.ADMIN):
            User.objects.create_user(f"{role.value.lower()}@hms.local", PASSWORD, role=role)
            self.client.login(email=f"{role.value.lower()}@hms.local", password=PASSWORD)
            self.assertEqual(self.client.get(self.url).status_code, 403, role)
            self.client.logout()

    def test_tc08_student_gets_404_on_another_students_application(self):
        self.apply()
        application = RoomApplication.objects.get()
        other = make_student(5)
        self.client.login(email=other.user.email, password=PASSWORD)
        self.assertEqual(self.client.get(reverse("allocation:application_detail",
                                                 args=[application.application_no])).status_code, 404)
