from io import BytesIO
from pathlib import Path

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from PIL import Image

from apps.accounts.models import Role, User
from apps.allocation.models import Allocation, AllocationStatus
from apps.rooms.models import Hostel, Room, RoomType
from apps.students.models import Gender, StudentProfile


PASSWORD = "Strongpass2026"


class SecureProfileDeliveryTests(TestCase):
    def setUp(self):
        self.student = User.objects.create_user(
            email="issue33student@hms.local", password=PASSWORD, role=Role.STUDENT
        )
        self.other_student = User.objects.create_user(
            email="issue33other@hms.local", password=PASSWORD, role=Role.STUDENT
        )
        self.admin = User.objects.create_user(
            email="issue33admin@hms.local", password=PASSWORD, role=Role.ADMIN
        )
        self.profile = StudentProfile.objects.create(
            user=self.student,
            srn="PES1UG26CS901",
            name="Issue Thirty Three",
            gender=Gender.MALE,
            program="CSE",
            year=2,
            mobile="9876543210",
            personal_email="issue33@example.com",
            permanent_address="Bengaluru, Karnataka",
            guardian_name="Parent",
            guardian_relationship="Parent",
            guardian_mobile="9876543211",
            emergency_contact_name="Emergency",
            emergency_contact_mobile="9876543212",
            blood_group="A+",
        )
        self.other_profile = StudentProfile.objects.create(
            user=self.other_student,
            srn="PES1UG26CS902",
            name="Other Student",
            gender=Gender.FEMALE,
            program="ECE",
            year=1,
        )

    def make_png(self, name="profile.png"):
        buffer = BytesIO()
        Image.new("RGB", (2, 2), color="red").save(buffer, format="PNG")
        return SimpleUploadedFile(name, buffer.getvalue(), content_type="image/png")

    def upload_photo(self):
        self.client.force_login(self.student)
        response = self.client.post(
            reverse("students:profile_edit", args=[self.profile.pk]),
            {
                "mobile": "9876543210",
                "personal_email": "issue33@example.com",
                "permanent_address": "Bengaluru, Karnataka",
                "guardian_name": "Parent",
                "guardian_relationship": "Parent",
                "guardian_mobile": "9876543211",
                "emergency_contact_name": "Emergency",
                "emergency_contact_mobile": "9876543212",
                "blood_group": "A+",
                "photo": self.make_png("../../unsafe.png"),
            },
        )
        self.assertEqual(response.status_code, 302)
        self.profile.refresh_from_db()

    def test_uploaded_photo_uses_randomized_filename(self):
        self.upload_photo()
        self.assertRegex(Path(self.profile.photo.name).name, r"^[0-9a-f]{32}\.png$")
        self.assertNotIn("..", self.profile.photo.name)

    def test_student_can_download_own_photo(self):
        self.upload_photo()
        response = self.client.get(
            reverse("students:profile_photo", args=[self.profile.pk])
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "image/png")
        self.assertEqual(response["Content-Disposition"], "inline")
        self.assertTrue(response.streaming_content)

    def test_student_cannot_download_another_students_photo(self):
        self.upload_photo()
        self.client.force_login(self.other_student)
        response = self.client.get(
            reverse("students:profile_photo", args=[self.profile.pk])
        )
        self.assertEqual(response.status_code, 404)

    def test_admin_can_download_any_students_photo(self):
        self.upload_photo()
        self.client.force_login(self.admin)
        response = self.client.get(
            reverse("students:profile_photo", args=[self.profile.pk])
        )
        self.assertEqual(response.status_code, 200)

    def test_missing_photo_returns_404(self):
        self.client.force_login(self.student)
        response = self.client.get(
            reverse("students:profile_photo", args=[self.profile.pk])
        )
        self.assertEqual(response.status_code, 404)

    def test_student_can_download_own_profile_pdf(self):
        self.client.force_login(self.student)
        response = self.client.get(
            reverse("students:profile_export_pdf", args=[self.profile.pk])
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertIn("attachment; filename=", response["Content-Disposition"])
        body = b"".join(response.streaming_content)
        self.assertTrue(body.startswith(b"%PDF-1.4"))
        self.assertIn(b"Issue Thirty Three", body)
        self.assertIn(b"PES1UG26CS901", body)

    def test_student_cannot_download_another_students_profile_pdf(self):
        self.client.force_login(self.student)
        response = self.client.get(
            reverse("students:profile_export_pdf", args=[self.other_profile.pk])
        )
        self.assertEqual(response.status_code, 404)

    def test_admin_can_download_any_profile_pdf(self):
        self.client.force_login(self.admin)
        response = self.client.get(
            reverse("students:profile_export_pdf", args=[self.profile.pk])
        )
        self.assertEqual(response.status_code, 200)

    def test_profile_pdf_contains_allocation_data(self):
        hostel = Hostel.objects.create(name="Issue 33 Hostel", gender_type=Gender.MALE)
        room = Room.objects.create(
            hostel=hostel,
            room_no="A101",
            floor=1,
            room_type=RoomType.DOUBLE,
            capacity=2,
            annual_fee="50000.00",
        )
        Allocation.objects.create(
            student=self.profile,
            room=room,
            bed_no=1,
            academic_year="2026-2027",
            start_date="2026-06-01",
            status=AllocationStatus.CONFIRMED,
        )
        self.client.force_login(self.student)
        response = self.client.get(
            reverse("students:profile_export_pdf", args=[self.profile.pk])
        )
        body = b"".join(response.streaming_content)
        self.assertIn(b"Issue 33 Hostel", body)
        self.assertIn(b"A101", body)
        self.assertIn(b"2026-2027", body)
        self.assertIn(b"Confirmed", body)

    def test_photo_is_stored_under_private_media(self):
        self.upload_photo()
        media_root = Path(self.profile.photo.storage.location).resolve()
        photo_path = Path(self.profile.photo.path).resolve()
        photo_path.relative_to(media_root)
