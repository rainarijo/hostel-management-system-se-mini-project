"""Tests for FR-1.4 / SEC-REQ-4: role-based access (Test Plan TC-04)."""
from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import Role, User

PASSWORD = "Strongpass2026"


class RoleAccessTests(TestCase):
    def setUp(self):
        for role in Role:
            User.objects.create_user(f"{role.value.lower()}@hms.local", PASSWORD, role=role)

    def login(self, role):
        self.client.login(email=f"{role.value.lower()}@hms.local", password=PASSWORD)

    def test_tc04_each_role_lands_on_its_own_dashboard(self):
        expected = {Role.STUDENT: "core:student_dashboard", Role.WARDEN: "core:warden_dashboard",
                    Role.ADMIN: "core:admin_dashboard"}
        for role, url_name in expected.items():
            self.login(role)
            self.assertRedirects(self.client.get(reverse("core:home")), reverse(url_name))
            self.client.logout()

    def test_tc04_student_cannot_open_warden_or_admin_pages(self):
        self.login(Role.STUDENT)
        for name in ("core:warden_dashboard", "core:admin_dashboard", "rooms:index", "reports:index"):
            self.assertEqual(self.client.get(reverse(name)).status_code, 403, name)

    def test_tc04_anonymous_user_is_sent_to_login(self):
        resp = self.client.get(reverse("core:warden_dashboard"))
        self.assertEqual(resp.status_code, 302)
        self.assertIn(reverse("accounts:login"), resp["Location"])
