"""Tests for FR-4.1: application window."""
from datetime import date

from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import Role, User
from apps.allocation.models import ApplicationWindow
from apps.allocation.services import get_open_window, require_open_window
from apps.core.exceptions import WindowClosed
from apps.core.models import AuditLog

PASSWORD = "Strongpass2026"


class ApplicationWindowTests(TestCase):
    def setUp(self):
        for role in Role:
            User.objects.create_user(f"{role.value.lower()}@hms.local", PASSWORD, role=role)

    def login(self, role):
        self.client.login(email=f"{role.value.lower()}@hms.local", password=PASSWORD)

    def post_window(self, year="2026-2027", start="2026-06-01", end="2026-06-30"):
        self.login(Role.ADMIN)
        return self.client.post(reverse("allocation:window_create"),
                                {"academic_year": year, "start_date": start, "end_date": end})

    def make_window(self):
        return ApplicationWindow.objects.create(academic_year="2026-2027", start_date=date(2026, 6, 1),
                                                end_date=date(2026, 6, 30))

    def test_fr41_admin_can_create_window(self):
        resp = self.post_window()
        self.assertRedirects(resp, reverse("allocation:window_list"))
        window = ApplicationWindow.objects.get(academic_year="2026-2027")
        self.assertEqual(window.created_by.email, "admin@hms.local")
        self.assertTrue(AuditLog.objects.filter(action="WINDOW_CREATED", entity_id=str(window.pk)).exists())
        self.assertContains(self.client.get(reverse("allocation:window_list")), "01-06-2026")

    def test_fr41_admin_can_edit_window_and_change_is_audited(self):
        window = self.make_window()
        self.login(Role.ADMIN)
        resp = self.client.post(reverse("allocation:window_edit", args=[window.pk]),
                                {"academic_year": "2026-2027", "start_date": "2026-06-01", "end_date": "2026-07-15"})
        self.assertRedirects(resp, reverse("allocation:window_list"))
        window.refresh_from_db()
        self.assertEqual(window.end_date, date(2026, 7, 15))
        entry = AuditLog.objects.get(action="WINDOW_UPDATED")
        self.assertIn("30-06-2026", entry.old_value)
        self.assertIn("15-07-2026", entry.new_value)

    def test_fr41_duplicate_academic_year_rejected(self):
        self.make_window()
        resp = self.post_window(start="2026-08-01", end="2026-08-31")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("already exists", resp.context["form"].errors["academic_year"][0])
        self.assertEqual(ApplicationWindow.objects.count(), 1)

    def test_fr41_end_before_start_rejected(self):
        resp = self.post_window(start="2026-06-30", end="2026-06-01")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("end_date", resp.context["form"].errors)
        self.assertFalse(ApplicationWindow.objects.exists())

    def test_fr41_bad_year_format_rejected(self):
        for bad in ("2026", "2026-2028", "26-27", "2027-2026"):
            resp = self.post_window(year=bad)
            self.assertEqual(resp.context["form"].errors["academic_year"], ["Enter the year as 2026-2027."], bad)
        self.assertFalse(ApplicationWindow.objects.exists())

    def test_fr41_student_and_warden_get_403(self):
        for role in (Role.STUDENT, Role.WARDEN):
            self.login(role)
            for name in ("allocation:window_list", "allocation:window_create"):
                self.assertEqual(self.client.get(reverse(name)).status_code, 403, (role, name))
            self.client.logout()

    def test_fr41_get_open_window_inside_and_outside_dates(self):
        window = self.make_window()
        self.assertEqual(get_open_window(date(2026, 6, 1)), window)
        self.assertEqual(get_open_window(date(2026, 6, 30)), window)
        self.assertIsNone(get_open_window(date(2026, 5, 31)))
        self.assertIsNone(get_open_window(date(2026, 7, 1)))

    def test_fr41_require_open_window_raises_outside(self):
        window = self.make_window()
        self.assertEqual(require_open_window(date(2026, 6, 15)), window)
        with self.assertRaises(WindowClosed):
            require_open_window(date(2026, 7, 1))
