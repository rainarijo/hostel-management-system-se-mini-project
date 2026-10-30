import hashlib
from datetime import timedelta

from django.core import mail
from django.core.cache import cache
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import AuthToken, TokenPurpose, User
from apps.students.models import StudentProfile


PASSWORD = "Strongpass2026"


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    CACHES={
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "password-reset-tests",
        }
    },
)
class PasswordResetTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(
            email="student@hms.local",
            password=PASSWORD,
            is_active=True,
        )
        self.request_url = reverse("accounts:password_reset")

    def request_reset(self, email):
        response = self.client.post(
            self.request_url,
            {"email": email},
        )
        # Issue #30 queues the reset mail. Dispatch it explicitly in tests
        # before asserting against the locmem mail backend.
        call_command("send_pending_notifications")
        return response

    def get_token_from_email(self):
        self.assertEqual(len(mail.outbox), 1)
        body = mail.outbox[0].body
        link = next(
            line.strip()
            for line in body.splitlines()
            if "/accounts/password-reset/" in line
        )
        return link.rstrip("/").split("/")[-1]

    def test_request_sends_reset_email_to_active_user(self):
        response = self.request_reset(self.user.email)

        self.assertRedirects(
            response,
            self.request_url,
            fetch_redirect_response=False,
        )
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, [self.user.email])

        token = self.get_token_from_email()
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        auth_token = AuthToken.objects.get(
            token_hash=token_hash,
            purpose=TokenPurpose.RESET,
        )
        self.assertTrue(auth_token.is_valid)
        self.assertLessEqual(
            auth_token.expires_at - timezone.now(),
            timedelta(minutes=30),
        )

    def test_unknown_email_gets_same_public_response(self):
        known_response = self.request_reset(self.user.email)
        cache.clear()
        unknown_response = self.request_reset("unknown@hms.local")

        self.assertEqual(known_response.status_code, 302)
        self.assertEqual(unknown_response.status_code, 302)
        self.assertEqual(len(mail.outbox), 1)

    def test_reset_token_changes_password_and_cannot_be_reused(self):
        self.request_reset(self.user.email)
        token = self.get_token_from_email()
        confirm_url = reverse(
            "accounts:password_reset_confirm",
            args=[token],
        )

        response = self.client.post(
            confirm_url,
            {
                "password1": "AnotherStrong2026",
                "password2": "AnotherStrong2026",
            },
        )

        self.assertRedirects(
            response,
            reverse("accounts:login"),
            fetch_redirect_response=False,
        )
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("AnotherStrong2026"))

        reused_response = self.client.get(confirm_url)
        self.assertEqual(reused_response.status_code, 400)

    def test_expired_token_is_rejected(self):
        self.request_reset(self.user.email)
        token = self.get_token_from_email()
        token_hash = hashlib.sha256(token.encode()).hexdigest()

        auth_token = AuthToken.objects.get(token_hash=token_hash)
        auth_token.expires_at = timezone.now() - timedelta(seconds=1)
        auth_token.save(update_fields=["expires_at"])

        response = self.client.get(
            reverse("accounts:password_reset_confirm", args=[token])
        )
        self.assertEqual(response.status_code, 400)

    def test_reset_request_is_limited_to_five_per_email_per_hour(self):
        for _ in range(6):
            self.request_reset(self.user.email)

        self.assertEqual(len(mail.outbox), 5)

    def test_password_mismatch_does_not_change_password(self):
        self.request_reset(self.user.email)
        token = self.get_token_from_email()

        response = self.client.post(
            reverse("accounts:password_reset_confirm", args=[token]),
            {
                "password1": "FirstStrong2026",
                "password2": "SecondStrong2026",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(PASSWORD))

    def test_password_containing_srn_is_rejected_on_reset(self):
        self.request_reset(self.user.email)
        token = self.get_token_from_email()

        StudentProfile.objects.create(
            user=self.user,
            srn="PES1UG24CS999",
            name="Reset Student",
            gender="M",
            program="CSE",
            year=2,
        )

        response = self.client.post(
            reverse("accounts:password_reset_confirm", args=[token]),
            {
                "password1": "PES1UG24CS999Strong2026!",
                "password2": "PES1UG24CS999Strong2026!",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(PASSWORD))
