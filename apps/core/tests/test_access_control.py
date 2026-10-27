"""Tests for FR-1.4 / SEC-REQ-4: role-based access (Test Plan TC-04)."""
from django.test import TestCase
from django.urls import reverse
from apps.core.models import AuditLog
from apps.accounts.models import Role, User
from django.contrib.admin.sites import AdminSite
from django.test import RequestFactory
from apps.core.admin import AuditLogAdmin
from datetime import timedelta
from django.core.management import call_command
from django.utils import timezone

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


class AuditLogIntegrityTests(TestCase):
    def test_audit_log_entry_cannot_be_updated(self):
        entry = AuditLog.objects.create(
            action="TEST_ACTION",
            entity="test_entity",
            entity_id="123",
            old_value="old",
            new_value="new",
        )

        entry.new_value = "tampered"

        with self.assertRaises(ValueError):
            entry.save()

    def test_audit_log_entry_cannot_be_deleted(self):
        entry = AuditLog.objects.create(
            action="TEST_ACTION",
            entity="test_entity",
            entity_id="123",
        )

        with self.assertRaises(ValueError):
            entry.delete()

        self.assertTrue(AuditLog.objects.filter(pk=entry.pk).exists())

    def test_audit_log_entries_cannot_be_bulk_deleted(self):
        entry = AuditLog.objects.create(
            action="TEST_ACTION",
            entity="test_entity",
            entity_id="456",
        )

        with self.assertRaises(ValueError):
            AuditLog.objects.filter(pk=entry.pk).delete()

        self.assertTrue(
            AuditLog.objects.filter(pk=entry.pk).exists()
        )

    def test_audit_log_entries_cannot_be_bulk_updated(self):
        entry = AuditLog.objects.create(
            action="TEST_ACTION",
            entity="test_entity",
            entity_id="789",
            new_value="original",
        )

        with self.assertRaises(ValueError):
            AuditLog.objects.filter(pk=entry.pk).update(
                new_value="tampered"
            )

        entry.refresh_from_db()
        self.assertEqual(entry.new_value, "original")


class AuditLogAdminPermissionTests(TestCase):
    def setUp(self):
        self.site = AdminSite()
        self.model_admin = AuditLogAdmin(AuditLog, self.site)
        self.factory = RequestFactory()

    def make_request(self, role, is_staff, is_superuser):
        user = User.objects.create_user(
            email=f"{role.lower()}-{is_staff}-{is_superuser}@hms.local",
            password=PASSWORD,
            role=role,
            is_staff=is_staff,
            is_superuser=is_superuser,
        )
        request = self.factory.get("/admin/core/auditlog/")
        request.user = user
        return request

    def test_only_active_admin_superuser_can_view_audit_logs(self):
        admin_request = self.make_request(Role.ADMIN, True, True)
        warden_request = self.make_request(Role.WARDEN, True, True)
        student_request = self.make_request(Role.STUDENT, True, True)
        non_superuser_request = self.make_request(Role.ADMIN, True, False)

        self.assertTrue(
            self.model_admin.has_view_permission(admin_request)
        )
        self.assertFalse(
            self.model_admin.has_view_permission(warden_request)
        )
        self.assertFalse(
            self.model_admin.has_view_permission(student_request)
        )
        self.assertFalse(
            self.model_admin.has_view_permission(non_superuser_request)
        )

    def test_audit_logs_cannot_be_added_changed_or_deleted_in_admin(self):
        request = self.make_request(Role.ADMIN, True, True)

        self.assertFalse(self.model_admin.has_add_permission(request))
        self.assertFalse(
            self.model_admin.has_change_permission(request)
        )
        self.assertFalse(
            self.model_admin.has_delete_permission(request)
        )


class AuditLogRetentionTests(TestCase):
    def test_retention_command_removes_old_logs_only(self):
        old_entry = AuditLog.objects.create(action="OLD_EVENT")
        recent_entry = AuditLog.objects.create(action="RECENT_EVENT")

        AuditLog._base_manager.filter(pk=old_entry.pk).update(
            timestamp=timezone.now() - timedelta(days=366)
        )

        call_command("purge_audit_logs", verbosity=0)

        self.assertFalse(
            AuditLog._base_manager.filter(pk=old_entry.pk).exists()
        )
        self.assertTrue(
            AuditLog.objects.filter(pk=recent_entry.pk).exists()
        )
