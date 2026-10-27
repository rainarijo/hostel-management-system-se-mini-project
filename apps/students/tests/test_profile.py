from io import BytesIO
from PIL import Image
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from apps.accounts.models import Role, User
from apps.students.models import Gender, StudentProfile
from datetime import date
from apps.allocation.models import Allocation, AllocationStatus
from apps.rooms.models import Hostel, Room, RoomType
PASSWORD = "Strongpass2026"


class StudentProfileTests(TestCase):
    def setUp(self):
        self.student = User.objects.create_user(
            email="student1@hms.local",
            password=PASSWORD,
            role=Role.STUDENT,
        )
        self.other_student = User.objects.create_user(
            email="student2@hms.local",
            password=PASSWORD,
            role=Role.STUDENT,
        )
        self.admin = User.objects.create_user(
            email="admin@hms.local",
            password=PASSWORD,
            role=Role.ADMIN,
        )

        self.profile = StudentProfile.objects.create(
            user=self.student,
            srn="PES1UG26CS001",
            name="Student One",
            gender=Gender.MALE,
            program="CSE",
            year=2,
        )
        self.other_profile = StudentProfile.objects.create(
            user=self.other_student,
            srn="PES1UG26CS002",
            name="Student Two",
            gender=Gender.FEMALE,
            program="ECE",
            year=1,
        )

    def test_student_can_view_own_profile(self):
        self.client.force_login(self.student)
        response = self.client.get(
            reverse("students:profile_detail", args=[self.profile.pk])
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Student One")
        self.assertContains(response, "PES1UG26CS001")

    def test_student_cannot_view_another_students_profile(self):
        self.client.force_login(self.student)
        response = self.client.get(
            reverse("students:profile_detail", args=[self.other_profile.pk])
        )
        self.assertEqual(response.status_code, 403)

    def test_student_can_edit_permitted_fields(self):
        self.client.force_login(self.student)
        response = self.client.post(
            reverse("students:profile_edit", args=[self.profile.pk]),
            {
                "mobile": "9876543210",
                "personal_email": "personal@example.com",
                "permanent_address": "Bengaluru, Karnataka",
                "guardian_name": "Parent One",
                "guardian_relationship": "Parent",
                "guardian_mobile": "9876543211",
                "emergency_contact_name": "Contact One",
                "emergency_contact_mobile": "9876543212",
                "blood_group": "A+",
            },
        )

        self.assertRedirects(
            response,
            reverse("students:profile_detail", args=[self.profile.pk]),
        )
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.mobile, "9876543210")
        self.assertEqual(self.profile.personal_email, "personal@example.com")
        self.assertEqual(self.profile.permanent_address, "Bengaluru, Karnataka")
        self.assertEqual(self.profile.guardian_name, "Parent One")
        self.assertEqual(self.profile.blood_group, "A+")

    def test_student_cannot_edit_another_students_profile(self):
        self.client.force_login(self.student)
        response = self.client.post(
            reverse("students:profile_edit", args=[self.other_profile.pk]),
            {"mobile": "9876543210"},
        )
        self.assertEqual(response.status_code, 403)
        self.other_profile.refresh_from_db()
        self.assertEqual(self.other_profile.mobile, "")

    def test_student_cannot_change_academic_fields_by_posting_them(self):
        self.client.force_login(self.student)
        response = self.client.post(
            reverse("students:profile_edit", args=[self.profile.pk]),
            {
                "srn": "PES1UG26CS999",
                "name": "Changed Name",
                "gender": Gender.FEMALE,
                "program": "ECE",
                "year": 4,
                "mobile": "9876543210",
                "personal_email": "student@example.com",
                "permanent_address": "Bengaluru, Karnataka",
                "guardian_name": "Parent One",
                "guardian_relationship": "Parent",
                "guardian_mobile": "9876543211",
                "emergency_contact_name": "Contact One",
                "emergency_contact_mobile": "9876543212",
                "blood_group": "A+",
            },
        )

        self.assertRedirects(
            response,
            reverse("students:profile_detail", args=[self.profile.pk]),
        )
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.srn, "PES1UG26CS001")
        self.assertEqual(self.profile.name, "Student One")
        self.assertEqual(self.profile.gender, Gender.MALE)
        self.assertEqual(self.profile.program, "CSE")
        self.assertEqual(self.profile.year, 2)

    def test_admin_can_edit_academic_fields(self):
        self.client.force_login(self.admin)
        response = self.client.post(
            reverse("students:profile_edit", args=[self.profile.pk]),
            {
                "srn": "PES1UG26CS001",
                "name": "Updated Student",
                "gender": Gender.MALE,
                "program": "CSE",
                "year": 3,
                "mobile": "9876543210",
                "personal_email": "student@example.com",
                "permanent_address": "Bengaluru, Karnataka",
                "guardian_name": "Parent One",
                "guardian_relationship": "Parent",
                "guardian_mobile": "9876543211",
                "emergency_contact_name": "Contact One",
                "emergency_contact_mobile": "9876543212",
                "blood_group": "A+",
            }
        )

        self.assertRedirects(
            response,
            reverse("students:profile_detail", args=[self.profile.pk]),
        )
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.year, 3)
        self.assertEqual(self.profile.name, "Updated Student")

    def test_invalid_mobile_number_is_rejected(self):
        self.client.force_login(self.student)
        response = self.client.post(
            reverse("students:profile_edit", args=[self.profile.pk]),
            {
                "mobile": "123",
                "personal_email": "",
                "permanent_address": "",
                "guardian_name": "",
                "guardian_relationship": "",
                "guardian_mobile": "",
                "emergency_contact_name": "",
                "emergency_contact_mobile": "",
                "blood_group": "",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.mobile, "")

    def test_student_edit_form_does_not_expose_academic_fields(self):
        self.client.force_login(self.student)
        response = self.client.get(
            reverse("students:profile_edit", args=[self.profile.pk])
        )

        self.assertEqual(response.status_code, 200)
        for field in ("srn", "name", "gender", "program", "year"):
            self.assertNotIn(field, response.context["form"].fields)

    def test_admin_edit_form_includes_academic_fields(self):
        self.client.force_login(self.admin)
        response = self.client.get(
            reverse("students:profile_edit", args=[self.profile.pk])
        )

        self.assertEqual(response.status_code, 200)
        for field in ("srn", "name", "gender", "program", "year"):
            self.assertIn(field, response.context["form"].fields)

    def test_student_can_upload_profile_photo(self):
        self.client.force_login(self.student)

        image_buffer = BytesIO()
        Image.new("RGB", (1, 1), color="red").save(
            image_buffer,
            format="PNG",
        )
        image_buffer.seek(0)

        photo = SimpleUploadedFile(
            "profile.png",
            image_buffer.read(),
            content_type="image/png",
        )

        response = self.client.post(
            reverse("students:profile_edit", args=[self.profile.pk]),
            {
                "mobile": "9876543210",
                "personal_email": "",
                "permanent_address": "Bengaluru, Karnataka",
                "guardian_name": "Parent One",
                "guardian_relationship": "Parent",
                "guardian_mobile": "9876543211",
                "emergency_contact_name": "Contact One",
                "emergency_contact_mobile": "9876543212",
                "blood_group": "A+",
                "photo": photo,
            },
        )

        self.assertRedirects(
            response,
            reverse("students:profile_detail", args=[self.profile.pk]),
        )
        self.profile.refresh_from_db()
        self.assertTrue(self.profile.photo)
        self.assertTrue(self.profile.photo.name.startswith("photos/"))


class StudentSearchTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            email="searchadmin@hms.local",
            password=PASSWORD,
            role=Role.ADMIN,
        )
        self.warden_a = User.objects.create_user(
            email="searchwarden1@hms.local",
            password=PASSWORD,
            role=Role.WARDEN,
        )
        self.warden_b = User.objects.create_user(
            email="searchwarden2@hms.local",
            password=PASSWORD,
            role=Role.WARDEN,
        )

        self.hostel_a = Hostel.objects.create(
            name="Search Hostel A",
            gender_type=Gender.MALE,
        )
        self.hostel_a.wardens.add(self.warden_a)

        self.hostel_b = Hostel.objects.create(
            name="Search Hostel B",
            gender_type=Gender.FEMALE,
        )
        self.hostel_b.wardens.add(self.warden_b)

        self.room_a = Room.objects.create(
            hostel=self.hostel_a,
            room_no="A101",
            floor=1,
            room_type=RoomType.DOUBLE,
            capacity=2,
            annual_fee="50000.00",
        )
        self.room_b = Room.objects.create(
            hostel=self.hostel_b,
            room_no="B202",
            floor=2,
            room_type=RoomType.DOUBLE,
            capacity=2,
            annual_fee="50000.00",
        )

        self.student_a = User.objects.create_user(
            email="searchstudent1@hms.local",
            password=PASSWORD,
            role=Role.STUDENT,
        )
        self.student_b = User.objects.create_user(
            email="searchstudent2@hms.local",
            password=PASSWORD,
            role=Role.STUDENT,
        )

        self.profile_a = StudentProfile.objects.create(
            user=self.student_a,
            srn="PES1UG26CS101",
            name="Alice Search",
            gender=Gender.MALE,
            program="CSE",
            year=2,
            mobile="9876543210",
            guardian_mobile="9876543211",
        )
        self.profile_b = StudentProfile.objects.create(
            user=self.student_b,
            srn="PES1UG26CS202",
            name="Bob Search",
            gender=Gender.FEMALE,
            program="ECE",
            year=1,
            mobile="9876543220",
            guardian_mobile="9876543221",
        )

        Allocation.objects.create(
            student=self.profile_a,
            room=self.room_a,
            bed_no=1,
            academic_year="2026-2027",
            start_date=date(2026, 6, 1),
            status=AllocationStatus.CONFIRMED,
        )
        Allocation.objects.create(
            student=self.profile_b,
            room=self.room_b,
            bed_no=1,
            academic_year="2026-2027",
            start_date=date(2026, 6, 1),
            status=AllocationStatus.CONFIRMED,
        )

    def test_admin_can_search_by_partial_srn(self):
        self.client.force_login(self.admin)

        response = self.client.get(
            reverse("students:search"),
            {"q": "CS101"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "PES1UG26CS101")
        self.assertNotContains(response, "PES1UG26CS202")

    def test_admin_can_search_name_case_insensitively(self):
        self.client.force_login(self.admin)

        response = self.client.get(
            reverse("students:search"),
            {"q": "ALICE"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Alice Search")
        self.assertNotContains(response, "Bob Search")

    def test_warden_only_sees_students_in_assigned_hostels(self):
        self.client.force_login(self.warden_a)

        response = self.client.get(reverse("students:search"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Alice Search")
        self.assertNotContains(response, "Bob Search")
        self.assertContains(response, "Search Hostel A")
        self.assertNotContains(response, "Search Hostel B")

    def test_warden_cannot_filter_into_another_hostel(self):
        self.client.force_login(self.warden_a)

        response = self.client.get(
            reverse("students:search"),
            {"hostel": str(self.hostel_b.pk)},
        )

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Alice Search")
        self.assertNotContains(response, "Bob Search")

    def test_warden_sees_only_authorized_room_details(self):
        self.client.force_login(self.warden_a)

        response = self.client.get(reverse("students:search"))

        self.assertContains(response, "A101")
        self.assertNotContains(response, "B202")
