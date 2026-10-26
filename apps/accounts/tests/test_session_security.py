
from django.conf import settings
from django.test import TestCase, override_settings
from django.urls import reverse

from apps.accounts.models import User


PASSWORD = "Strongpass2026"


class SessionSecurityTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="session@hms.local",
            password=PASSWORD,
            is_active=True,
        )

    def test_login_rotates_session_key(self):
        # Establish an anonymous session first.
        session = self.client.session
        session["before_login"] = "present"
        session.save()
        old_key = self.client.cookies[
            settings.SESSION_COOKIE_NAME
        ].value

        response = self.client.post(
            reverse("accounts:login"),
            {
                "email": self.user.email,
                "password": PASSWORD,
            },
        )

        self.assertEqual(response.status_code, 302)
        new_key = self.client.cookies[
            settings.SESSION_COOKIE_NAME
        ].value

        self.assertNotEqual(old_key, new_key)

    def test_logout_invalidates_session(self):
        self.client.login(
            email=self.user.email,
            password=PASSWORD,
        )

        self.assertIn(
            "_auth_user_id",
            self.client.session,
        )

        response = self.client.post(
            reverse("accounts:logout")
        )

        self.assertEqual(response.status_code, 302)
        self.assertNotIn(
            "_auth_user_id",
            self.client.session,
        )

    @override_settings(
        SESSION_COOKIE_SECURE=True,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
    )
    def test_session_cookie_security_settings(self):
        self.client.post(
            reverse("accounts:login"),
            {
                "email": self.user.email,
                "password": PASSWORD,
            },
        )

        cookie = self.client.cookies[
            settings.SESSION_COOKIE_NAME
        ]

        self.assertTrue(cookie["secure"])
        self.assertTrue(cookie["httponly"])
        self.assertEqual(cookie["samesite"], "Lax")

    def test_session_age_is_thirty_minutes(self):
        self.assertEqual(
            settings.SESSION_COOKIE_AGE,
            30 * 60,
        )

    def test_sessions_are_saved_on_each_request(self):
        self.assertTrue(settings.SESSION_SAVE_EVERY_REQUEST)
