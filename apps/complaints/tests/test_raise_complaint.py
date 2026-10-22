"""Test Plan TC-13 (FR-6.1, FR-6.2): raise a complaint."""
import re
from datetime import date

from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import Role, User
from apps.allocation.models import Allocation, AllocationStatus
from apps.complaints.models import Complaint, ComplaintStatus
from apps.complaints.services import raise_complaint
from apps.rooms.models import Hostel, Room, RoomType
from apps.students.models import StudentProfile

PASSWORD = "Hostel2026pass"
DESCRIPTION = "The ceiling fan in my room has stopped working completely."


def make_student(n, gender="M"):
    user = User.objects.create_user(f"tc13student{n}@hms.local", PASSWORD, role=Role.STUDENT,
                                    first_name="Test", last_name=f"Student{n}")
    profile = StudentProfile.objects.create(
        user=user, srn=f"PES1UG24CS9{n:02d}", name=f"Test Student{n}", gender=gender, program="B.Tech CSE",
        year=2, mobile=f"98450001{n:02d}", permanent_address="12, 4th Cross, Jayanagar, Bengaluru",
        guardian_name="Parent", guardian_relationship="Parent", guardian_mobile=f"98860001{n:02d}",
        blood_group="O+")
    return user, profile


def sequence_part(complaint):
    return int(re.search(r"(\d{5})$", complaint.complaint_no).group(1))


class RaiseComplaintTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.hostel = Hostel.objects.create(name="Test Block", gender_type="M")
        cls.room = Room.objects.create(hostel=cls.hostel, room_no="201", floor=2, room_type=RoomType.DOUBLE,
                                       capacity=2, annual_fee=75000)
        cls.user, cls.student = make_student(1)
        cls.alloc = Allocation.objects.create(student=cls.student, room=cls.room, bed_no=1,
                                              start_date=date.today(), academic_year="2026-2027")
        cls.other_user, cls.other_student = make_student(2)
        cls.url = reverse("complaints:index")

    def post_complaint(self, **overrides):
        data = {"category": "ELECTRICAL", "description": DESCRIPTION}
        data.update(overrides)
        return self.client.post(self.url, data)

    def test_tc13_student_with_allocation_can_raise_complaint(self):
        self.client.force_login(self.user)
        response = self.post_complaint()
        self.assertEqual(response.status_code, 302)
        complaint = Complaint.objects.get()
        self.assertEqual(complaint.student, self.student)
        self.assertEqual(complaint.room, self.room)           # FR-6.2: room copied from the allocation
        self.assertEqual(complaint.hostel, self.hostel)
        self.assertEqual(complaint.status, ComplaintStatus.OPEN)
        self.assertRegex(complaint.complaint_no, r"^CMP-\d{4}-\d{5}$")

    def test_tc13_complaint_numbers_are_unique_and_sequential(self):
        first = raise_complaint(self.user, self.student, "PLUMBING", DESCRIPTION)
        second = raise_complaint(self.user, self.student, "FURNITURE", DESCRIPTION)
        self.assertNotEqual(first.complaint_no, second.complaint_no)
        self.assertEqual(sequence_part(second), sequence_part(first) + 1)

    def test_tc13_student_without_active_allocation_is_blocked(self):
        self.client.force_login(self.other_user)
        response = self.post_complaint()
        self.assertEqual(response.status_code, 409)
        self.assertEqual(Complaint.objects.count(), 0)

    def test_tc13_ended_allocation_does_not_count(self):
        Allocation.objects.filter(pk=self.alloc.pk).update(status=AllocationStatus.ENDED)
        self.client.force_login(self.user)
        response = self.post_complaint()
        self.assertEqual(response.status_code, 409)
        self.assertEqual(Complaint.objects.count(), 0)

    def test_tc13_short_description_is_rejected(self):
        self.client.force_login(self.user)
        response = self.post_complaint(description="Too short")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Complaint.objects.count(), 0)
        self.assertContains(response, "at least 20 characters")

    def test_tc13_missing_category_is_rejected(self):
        self.client.force_login(self.user)
        response = self.post_complaint(category="")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Complaint.objects.count(), 0)
        self.assertContains(response, "Select a category.")

    def test_tc13_student_sees_only_own_complaints(self):
        mine = raise_complaint(self.user, self.student, "ELECTRICAL", DESCRIPTION)
        Allocation.objects.create(student=self.other_student, room=self.room, bed_no=2,
                                  start_date=date.today(), academic_year="2026-2027")
        theirs = raise_complaint(self.other_user, self.other_student, "PLUMBING", DESCRIPTION)
        self.client.force_login(self.user)
        response = self.client.get(self.url)
        self.assertContains(response, mine.complaint_no)
        self.assertNotContains(response, theirs.complaint_no)

    def test_tc13_warden_sees_placeholder_not_student_form(self):
        warden = User.objects.create_user("tc13warden@hms.local", PASSWORD, role=Role.WARDEN,
                                          first_name="W", last_name="Arden")
        self.client.force_login(warden)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Raise a complaint")

    def test_tc13_anonymous_user_is_sent_to_login(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertIn("login", response["Location"])
