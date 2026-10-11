"""Tests for FR-1.3, FR-1.5, FR-1.7. Test case IDs follow the Test Plan (TC-02, TC-03)."""
from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import Role, User
from apps.core.models import AuditLog

PASSWORD = "Strongpass2026"


class LoginTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("stu@hms.local", PASSWORD, role=Role.STUDENT)
        self.url = reverse("accounts:login")

    def test_tc02_valid_login_redirects_to_dashboard(self):
        resp = self.client.post(self.url, {"email": "stu@hms.local", "password": PASSWORD})
        self.assertRedirects(resp, reverse("core:home"), fetch_redirect_response=False)
        self.assertTrue(AuditLog.objects.filter(action="LOGIN_SUCCESS").exists())

    def test_tc02_same_error_for_unknown_email_and_wrong_password(self):
        r1 = self.client.post(self.url, {"email": "nobody@hms.local", "password": PASSWORD})
        r2 = self.client.post(self.url, {"email": "stu@hms.local", "password": "Wrongpass99"})
        self.assertContains(r1, "Invalid e-mail or password.")
        self.assertContains(r2, "Invalid e-mail or password.")

    def test_tc03_account_locks_after_five_failures(self):
        for _ in range(5):
            self.client.post(self.url, {"email": "stu@hms.local", "password": "Wrongpass99"})
        self.user.refresh_from_db()
        self.assertTrue(self.user.is_locked)
        # Even the correct password is refused while locked
        resp = self.client.post(self.url, {"email": "stu@hms.local", "password": PASSWORD})
        self.assertContains(resp, "temporarily locked")

    def test_logout_requires_post_and_ends_session(self):
        self.client.login(email="stu@hms.local", password=PASSWORD)
        self.assertEqual(self.client.get(reverse("accounts:logout")).status_code, 405)
        self.client.post(reverse("accounts:logout"))
        resp = self.client.get(reverse("core:home"))
        self.assertEqual(resp.status_code, 302)
        self.assertIn(reverse("accounts:login"), resp["Location"])
