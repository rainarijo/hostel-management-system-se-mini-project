from datetime import date

from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import Role, User
from apps.allocation.models import Allocation, AllocationStatus
from apps.rooms.models import Hostel, Room, RoomStatus
from apps.students.models import StudentProfile


class RoomAvailabilityTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user("admin@hms.local", "Strongpass2026", role=Role.ADMIN)
        self.warden = User.objects.create_user("warden@hms.local", "Strongpass2026", role=Role.WARDEN)
        self.student_user = User.objects.create_user("student@hms.local", "Strongpass2026", role=Role.STUDENT)
        self.student = StudentProfile.objects.create(
            user=self.student_user, srn="PES1UG24CS361", name="Student", gender="M", program="CSE", year=2,
        )
        self.hostel = Hostel.objects.create(name="North Hall", gender_type="M")
        self.hostel.wardens.add(self.warden)
        self.other_hostel = Hostel.objects.create(name="South Hall", gender_type="F")
        self.room = self.create_room("101", "DOUBLE", 2)
        self.create_room("102", "SINGLE", 1, status=RoomStatus.MAINTENANCE)
        self.create_room("201", "SINGLE", 1, hostel=self.other_hostel)
        Allocation.objects.create(
            student=self.student, room=self.room, bed_no=1, start_date=date.today(),
            status=AllocationStatus.CONFIRMED,
        )

    def create_room(self, room_no, room_type, capacity, hostel=None, status=RoomStatus.AVAILABLE):
        return Room.objects.create(
            hostel=hostel or self.hostel, room_no=room_no, floor=1, room_type=room_type,
            capacity=capacity, annual_fee=75000, status=status,
        )

    def test_staff_api_returns_room_details_and_active_allocation_occupancy(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse("room_availability_api"))
        self.assertEqual(response.status_code, 200)
        room = next(item for item in response.json()["rooms"] if item["room_no"] == "101")
        self.assertEqual(
            (room["capacity"], room["occupied"], room["vacant"], room["room_type"]),
            (2, 1, 1, "Double"),
        )

    def test_api_filters_and_rejects_invalid_query_values(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse("room_availability_api"), {
            "hostel": self.hostel.pk, "floor": 1, "room_type": "Double",
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual([room["room_no"] for room in response.json()["rooms"]], ["101"])

        for query in ({"floor": 21}, {"floor": "upper"}, {"room_type": "QUADRUPLE"}, {"unknown": "x"}):
            with self.subTest(query=query):
                self.assertEqual(
                    self.client.get(reverse("room_availability_api"), query).status_code,
                    400,
                )

    def test_warden_cannot_query_hostel_outside_assigned_scope(self):
        self.client.force_login(self.warden)
        response = self.client.get(reverse("room_availability_api"), {"hostel": self.other_hostel.pk})
        self.assertEqual(response.status_code, 404)
        self.assertEqual(
            {room["hostel_id"] for room in self.client.get(reverse("room_availability_api")).json()["rooms"]},
            {self.hostel.pk},
        )

    def test_student_receives_only_gender_scoped_vacancy_counts(self):
        self.client.force_login(self.student_user)
        response = self.client.get(reverse("room_availability_api"))
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["vacancy_by_type"], {"Single": 0, "Double": 1, "Triple": 0})
        self.assertNotIn("rooms", payload)
        self.assertNotIn("room_no", response.content.decode())

    def test_student_cannot_filter_to_hostel_of_another_gender(self):
        self.client.force_login(self.student_user)
        response = self.client.get(reverse("room_availability_api"), {"hostel": self.other_hostel.pk})
        self.assertEqual(response.status_code, 404)

    def test_anonymous_api_request_returns_json_401(self):
        response = self.client.get(reverse("room_availability_api"))
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["error"], "UNAUTHENTICATED")

    def test_staff_grid_page_renders_room_level_vacancy_data(self):
        self.client.force_login(self.warden)
        response = self.client.get(reverse("rooms:room_grid"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "North Hall")
        self.assertContains(response, "101")
        self.assertNotContains(response, "South Hall")
