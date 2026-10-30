from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core import mail
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import AuthToken, TokenPurpose
from apps.students.models import MasterStudent, StudentProfile


User = get_user_model()


class RegistrationTests(TestCase):
    def setUp(self):
        self.student = MasterStudent.objects.create(
            srn="PES1UG24CS999",
            name="Test Student",
            gender="M",
            program="CSE",
            year=2,
            email="teststudent999@hms.local",
        )
        self.url = reverse("accounts:register")
        self.data = {
            "srn": self.student.srn,
            "email": self.student.email,
            "password1": "SecureTestPass2026!",
            "password2": "SecureTestPass2026!",
        }

    def register_student(self):
        response = self.client.post(self.url, self.data)

        # Issue #30 queues verification mail in the same transaction as
        # registration. Dispatch it before inspecting the test mail backend.
        call_command("send_pending_notifications")

        user = User.objects.get(email=self.student.email)
        token = AuthToken.objects.get(
            user=user,
            purpose=TokenPurpose.VERIFY,
        )
        raw_token = mail.outbox[0].body.split(
            "/accounts/verify/"
        )[1].split()[0].rstrip("/")
        return response, user, token, raw_token

    def test_valid_registration_creates_inactive_account_and_profile(self):
        response, user, token, raw_token = self.register_student()

        self.assertRedirects(response, reverse("accounts:login"))
        self.assertFalse(user.is_active)
        self.assertEqual(
            StudentProfile.objects.get(user=user).srn,
            self.student.srn,
        )
        self.assertTrue(token.is_valid)
        self.assertAlmostEqual(
            (token.expires_at - timezone.now()).total_seconds(),
            86400,
            delta=10,
        )
        self.assertTrue(raw_token)
        self.assertEqual(len(mail.outbox), 1)

    def test_unknown_srn_or_mismatched_email_is_rejected(self):
        self.data["email"] = "wrongemail@hms.local"

        response = self.client.post(self.url, self.data)

        self.assertContains(
            response,
            "SRN not found or already registered",
        )
        self.assertFalse(
            User.objects.filter(email=self.student.email).exists()
        )

    def test_duplicate_registration_is_rejected(self):
        user = User.objects.create_user(
            email=self.student.email,
            password="ExistingPass2026!",
        )
        StudentProfile.objects.create(
            user=user,
            srn=self.student.srn,
            name=self.student.name,
            gender=self.student.gender,
            program=self.student.program,
            year=self.student.year,
        )

        response = self.client.post(self.url, self.data)

        self.assertContains(
            response,
            "SRN not found or already registered",
        )
        self.assertEqual(
            User.objects.filter(email=self.student.email).count(),
            1,
        )

    def test_valid_verification_activates_account_once(self):
        response, user, token, raw_token = self.register_student()

        response = self.client.get(
            reverse("accounts:verify_email", args=[raw_token])
        )
        user.refresh_from_db()
        token.refresh_from_db()

        self.assertRedirects(response, reverse("accounts:login"))
        self.assertTrue(user.is_active)
        self.assertIsNotNone(token.used_at)

        response = self.client.get(
            reverse("accounts:verify_email", args=[raw_token])
        )
        user.refresh_from_db()

        self.assertFalse(
            AuthToken.objects.filter(
                pk=token.pk,
                used_at__isnull=True,
            ).exists()
        )
        self.assertFalse(
            response.wsgi_request.user.is_authenticated
        )

    def test_expired_verification_token_does_not_activate_account(self):
        response, user, token, raw_token = self.register_student()

        token.expires_at = timezone.now() - timedelta(seconds=1)
        token.save(update_fields=["expires_at"])

        response = self.client.get(
            reverse("accounts:verify_email", args=[raw_token])
        )
        user.refresh_from_db()

        self.assertRedirects(response, reverse("accounts:login"))
        self.assertFalse(user.is_active)
        self.assertIsNotNone(response.wsgi_request._messages)

    def test_password_containing_srn_is_rejected(self):
        self.data["password1"] = "PES1UG24CS999Strong2026!"
        self.data["password2"] = "PES1UG24CS999Strong2026!"

        response = self.client.post(self.url, self.data)

        self.assertEqual(response.status_code, 200)
        self.assertFalse(
            User.objects.filter(email=self.student.email).exists()
        )
