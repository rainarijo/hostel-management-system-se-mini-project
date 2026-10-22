
from io import BytesIO

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase
from PIL import Image

from apps.students.forms import StudentProfileForm


class StudentProfileValidationTests(SimpleTestCase):
    def valid_data(self, **overrides):
        data = {
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
        data.update(overrides)
        return data

    def test_valid_profile_data_is_accepted(self):
        form = StudentProfileForm(data=self.valid_data())
        self.assertTrue(form.is_valid(), form.errors)

    def test_mobile_must_be_ten_digits_starting_with_6_to_9(self):
        invalid_numbers = [
            "1234567890",
            "5123456789",
            "987654321",
            "98765432100",
            "98A6543210",
        ]

        for number in invalid_numbers:
            with self.subTest(number=number):
                form = StudentProfileForm(
                    data=self.valid_data(mobile=number)
                )
                self.assertFalse(form.is_valid())
                self.assertIn("mobile", form.errors)

    def test_guardian_mobile_must_be_valid(self):
        form = StudentProfileForm(
            data=self.valid_data(guardian_mobile="123")
        )
        self.assertFalse(form.is_valid())
        self.assertIn("guardian_mobile", form.errors)

    def test_emergency_mobile_must_be_valid(self):
        form = StudentProfileForm(
            data=self.valid_data(emergency_contact_mobile="123")
        )
        self.assertFalse(form.is_valid())
        self.assertIn("emergency_contact_mobile", form.errors)

    def test_invalid_email_is_rejected(self):
        form = StudentProfileForm(
            data=self.valid_data(personal_email="not-an-email")
        )
        self.assertFalse(form.is_valid())
        self.assertIn("personal_email", form.errors)

    def test_address_shorter_than_ten_characters_is_rejected(self):
        form = StudentProfileForm(
            data=self.valid_data(permanent_address="Bengaluru")
        )
        self.assertFalse(form.is_valid())
        self.assertIn("permanent_address", form.errors)

    def test_address_longer_than_250_characters_is_rejected(self):
        form = StudentProfileForm(
            data=self.valid_data(permanent_address="A" * 251)
        )
        self.assertFalse(form.is_valid())
        self.assertIn("permanent_address", form.errors)

    def test_blank_address_is_rejected(self):
        form = StudentProfileForm(
            data=self.valid_data(permanent_address="")
        )
        self.assertFalse(form.is_valid())
        self.assertIn("permanent_address", form.errors)

    def make_png(self):
        buffer = BytesIO()
        Image.new("RGB", (2, 2), color="red").save(buffer, format="PNG")
        return SimpleUploadedFile(
            "profile.png",
            buffer.getvalue(),
            content_type="image/png",
        )

    def test_valid_png_photo_is_accepted(self):
        form = StudentProfileForm(
            data=self.valid_data(),
            files={"photo": self.make_png()},
        )
        self.assertTrue(form.is_valid(), form.errors)

    def test_non_image_file_is_rejected(self):
        photo = SimpleUploadedFile(
            "fake.png",
            b"this is not an image",
            content_type="image/png",
        )
        form = StudentProfileForm(
            data=self.valid_data(),
            files={"photo": photo},
        )
        self.assertFalse(form.is_valid())
        self.assertIn("photo", form.errors)

    def test_photo_over_two_mb_is_rejected(self):
        photo = SimpleUploadedFile(
            "large.png",
            b"x" * (2 * 1024 * 1024 + 1),
            content_type="image/png",
        )
        form = StudentProfileForm(
            data=self.valid_data(),
            files={"photo": photo},
        )
        self.assertFalse(form.is_valid())
        self.assertIn("photo", form.errors)
