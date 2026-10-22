
from io import BytesIO
from PIL import Image
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import Role, User
from apps.students.models import Gender, StudentProfile


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
