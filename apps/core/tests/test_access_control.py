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


# ---------------------------------------------------------------------------
# TC-20: SEC-REQ-4 server-side authorisation, no IDOR (STP 5.1). See docs/SECURITY_AUDIT.md.
# ---------------------------------------------------------------------------

# Routes anyone may open without logging in (SRS FR-1.1, FR-1.2, FR-1.6).
PUBLIC_URLS = {
    "accounts:login",
    "accounts:register",
    "accounts:verify_email",
    "accounts:password_reset",
    "accounts:password_reset_confirm",
}
# Not public, but answers an anonymous caller with a JSON 401 instead of a login redirect.
API_URLS = {"room_availability_api"}


def _all_routes():
    """(route name, URL) for every named route, Django admin excluded. 999999 for ints, 'X' for strings."""
    from django.urls import URLResolver, get_resolver
    from django.urls.converters import IntConverter

    def walk(patterns, namespace=None):
        for p in patterns:
            if isinstance(p, URLResolver):
                if str(p.pattern).startswith(("django-admin", "static", "media")):
                    continue
                yield from walk(p.url_patterns, p.namespace or namespace)
            elif p.name:
                name = f"{namespace}:{p.name}" if namespace else p.name
                kwargs = {k: 999999 if isinstance(c, IntConverter) else "X"
                          for k, c in p.pattern.converters.items()}
                yield name, reverse(name, kwargs=kwargs)

    return sorted(set(walk(get_resolver().url_patterns)))


class RouteInventoryTests(TestCase):
    def test_tc20_every_non_public_route_requires_login(self):
        """Anonymous GET of every route must redirect to login (302) or be refused as a GET (405).

        PUBLIC_URLS allowlist (no login needed): accounts:login, accounts:register, accounts:verify_email,
        accounts:password_reset, accounts:password_reset_confirm.
        API_URLS (JSON 401 for anonymous callers): room_availability_api.
        There is no healthz or "registration done" route in hms/urls.py.
        """
        login_url = reverse("accounts:login")
        routes = _all_routes()
        self.assertGreater(len(routes), 50)
        for name, url in routes:
            if name in PUBLIC_URLS:
                continue
            with self.subTest(route=name, url=url):
                resp = self.client.get(url)
                if name in API_URLS:
                    self.assertEqual(resp.status_code, 401)
                elif resp.status_code == 302:
                    self.assertTrue(resp["Location"].startswith(login_url), resp["Location"])
                else:
                    self.assertEqual(resp.status_code, 405)

    def test_tc20_allowlists_name_real_routes(self):
        names = {name for name, _ in _all_routes()}
        self.assertLessEqual(PUBLIC_URLS | API_URLS, names)


def _make_student(email, srn, gender="M", name=None):
    from apps.students.models import StudentProfile

    user = User.objects.create_user(email, PASSWORD, role=Role.STUDENT)
    return StudentProfile.objects.create(user=user, srn=srn, name=name or srn, gender=gender,
                                         program="B.Tech CSE", year=2)


class RoleMatrixTests(TestCase):
    """BR-1: each role is refused (403) on pages outside its role; every refusal is logged."""

    def setUp(self):
        from apps.allocation.models import ApplicationWindow, RoomApplication
        from apps.rooms.models import Hostel, Room

        self.student = _make_student("student.a@hms.local", "PES1UG24CS001")
        self.warden = User.objects.create_user("warden.boys@hms.local", PASSWORD, role=Role.WARDEN)
        self.admin = User.objects.create_user("admin@hms.local", PASSWORD, role=Role.ADMIN)
        self.hostel = Hostel.objects.create(name="Cauvery Block", gender_type="M")
        self.hostel.wardens.add(self.warden)
        self.room = Room.objects.create(hostel=self.hostel, room_no="101", floor=1, room_type="SINGLE", capacity=1,
                                        annual_fee=80000)
        self.window = ApplicationWindow.objects.create(academic_year="2026-2027", start_date=timezone.localdate(),
                                                       end_date=timezone.localdate())
        self.application = RoomApplication.objects.create(student=self.student, academic_year="2026-2027",
                                                          preference_1="SINGLE", application_no="APP-2026-00001")

    def staff_urls(self):
        """Warden + Admin pages (BR-1 'Warden and Admin')."""
        return [
            reverse("allocation:queue"),
            reverse("allocation:allocate", args=[self.application.pk]),
            reverse("allocation:change_request_queue"),
            reverse("allocation:history_manage"),
            reverse("rooms:index"),
            reverse("rooms:room_grid"),
            reverse("students:search"),
            reverse("fees:provisional_unpaid"),
            reverse("reports:index"),
            reverse("reports:detail", args=["occupancy"]),
            reverse("reports:export", args=["occupancy", "csv"]),
            reverse("core:warden_dashboard"),
        ]

    def admin_urls(self):
        """Admin-only pages (BR-1 'Admin only')."""
        return [
            reverse("allocation:window_list"),
            reverse("allocation:window_create"),
            reverse("allocation:window_edit", args=[self.window.pk]),
            reverse("rooms:hostel_create"),
            reverse("rooms:hostel_edit", args=[self.hostel.pk]),
            reverse("rooms:room_create"),
            reverse("rooms:room_edit", args=[self.room.pk]),
            reverse("room_import"),
            reverse("accounts:account_list"),
            reverse("accounts:account_create"),
            reverse("core:admin_dashboard"),
        ]

    def test_tc20_student_gets_403_on_warden_and_admin_pages(self):
        self.client.login(email="student.a@hms.local", password=PASSWORD)
        for url in self.staff_urls() + self.admin_urls():
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 403)
        # POST-only Admin actions are refused too, before any change is made.
        for url in (reverse("accounts:account_change_role", args=[self.admin.pk]),
                    reverse("accounts:account_deactivate", args=[self.admin.pk]),
                    reverse("rooms:hostel_deactivate", args=[self.hostel.pk]),
                    reverse("allocation:auto_allocate")):
            with self.subTest(url=url):
                self.assertEqual(self.client.post(url, {"hostel_id": self.hostel.pk}).status_code, 403)
        self.hostel.refresh_from_db()
        self.assertTrue(self.hostel.is_active)

    def test_tc20_student_cannot_view_audit_log(self):
        # The audit log is only reachable through the Django admin (superuser Administrators, see AuditLogAdmin).
        self.client.login(email="student.a@hms.local", password=PASSWORD)
        resp = self.client.get("/django-admin/core/auditlog/")
        self.assertEqual(resp.status_code, 302)
        self.assertIn("/django-admin/login/", resp["Location"])

    def test_tc20_warden_gets_403_on_admin_only_pages(self):
        self.client.login(email="warden.boys@hms.local", password=PASSWORD)
        for url in self.admin_urls():
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 403)

    def test_tc20_staff_pages_open_for_warden(self):
        # Guards the matrix itself: the 403s above come from the role, not from a broken page.
        self.client.login(email="warden.boys@hms.local", password=PASSWORD)
        for url in self.staff_urls():
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200)

    def test_tc20_role_denial_is_logged_without_personal_data(self):
        self.client.login(email="student.a@hms.local", password=PASSWORD)
        with self.assertLogs("hms.security", level="WARNING") as logs:
            self.client.get(reverse("allocation:queue"), {"q": "secret-query"})
        record = logs.records[0]
        self.assertEqual(record.levelname, "WARNING")
        self.assertEqual(record.security_event, "role_denied")
        self.assertEqual(record.user_id, self.student.user.pk)
        self.assertEqual((record.method, record.path), ("GET", reverse("allocation:queue")))
        text = logs.output[0]
        for leak in ("student.a@hms.local", "secret-query", PASSWORD, "sessionid"):
            self.assertNotIn(leak, text)
        self.assertTrue(AuditLog.objects.filter(action="ACCESS_DENIED").exists())


class IdorTests(TestCase):
    """STP 5.1: changing the id in a URL never exposes another student's data."""

    def setUp(self):
        from apps.allocation.models import Allocation, RoomApplication
        from apps.complaints.models import Complaint
        from apps.fees.models import Payment
        from apps.rooms.models import Hostel, Room

        self.a = _make_student("student.a@hms.local", "PES1UG24CS001", name="Asha Rao")
        self.b = _make_student("student.b@hms.local", "PES1UG24CS002", name="Bharat Iyer")
        self.girl = _make_student("student.g@hms.local", "PES1UG24CS003", gender="F", name="Gita Nair")
        self.warden_boys = User.objects.create_user("warden.boys@hms.local", PASSWORD, role=Role.WARDEN)
        admin = User.objects.create_user("admin@hms.local", PASSWORD, role=Role.ADMIN)
        boys = Hostel.objects.create(name="Cauvery Block", gender_type="M")
        boys.wardens.add(self.warden_boys)
        Hostel.objects.create(name="Kaveri Block", gender_type="F")
        room = Room.objects.create(hostel=boys, room_no="101", floor=1, room_type="DOUBLE", capacity=2,
                                   annual_fee=80000)

        self.b_application = RoomApplication.objects.create(
            student=self.b, academic_year="2026-2027", preference_1="DOUBLE", application_no="APP-2026-00002",
            status="ALLOCATED")
        self.girl_application = RoomApplication.objects.create(
            student=self.girl, academic_year="2026-2027", preference_1="SINGLE", application_no="APP-2026-00003")
        b_allocation = Allocation.objects.create(student=self.b, room=room, bed_no=1, application=self.b_application,
                                                 start_date=timezone.localdate())
        self.b_complaint = Complaint.objects.create(student=self.b, room=room, category="ELECTRICAL",
                                                    description="Fan not working.", status="RESOLVED",
                                                    resolved_at=timezone.now())
        self.b_payment = Payment.objects.create(fee_record=b_allocation.fee_record, receipt_no="RCP-2026-00001",
                                                amount=1000, mode="CASH", paid_on=timezone.localdate(),
                                                recorded_by=admin)

    def login_a(self):
        self.client.login(email="student.a@hms.local", password=PASSWORD)

    def assert_no_leak(self, resp):
        for secret in ("Bharat Iyer", "PES1UG24CS002"):
            self.assertNotIn(secret.encode(), resp.content)

    def test_tc20_student_cannot_open_other_students_application(self):
        self.login_a()
        with self.assertLogs("hms.security", level="WARNING") as logs:
            resp = self.client.get(reverse("allocation:application_detail", args=["APP-2026-00002"]))
        self.assertEqual(resp.status_code, 404)
        self.assert_no_leak(resp)
        self.assertEqual(logs.records[0].security_event, "not_found")

    def test_tc20_student_cannot_reopen_other_students_complaint(self):
        self.login_a()
        resp = self.client.post(reverse("complaints:reopen", args=[self.b_complaint.complaint_no]))
        self.assertEqual(resp.status_code, 404)
        self.b_complaint.refresh_from_db()
        self.assertEqual(self.b_complaint.status, "RESOLVED")

    def test_tc20_student_cannot_download_other_students_receipt(self):
        # SEC-REQ-4 wants 404 here; fees currently answers 403 (docs/SECURITY_AUDIT.md, problem F-1).
        self.login_a()
        with self.assertLogs("hms.security", level="WARNING"):
            resp = self.client.get(reverse("fees:receipt", args=[self.b_payment.receipt_no]))
        self.assertIn(resp.status_code, (403, 404))
        self.assertNotEqual(resp.get("Content-Type"), "application/pdf")
        self.assert_no_leak(resp)

    def test_tc20_student_cannot_open_other_students_profile(self):
        self.login_a()
        for name in ("students:profile_photo", "students:profile_export_pdf"):
            with self.subTest(route=name):
                resp = self.client.get(reverse(name, args=[self.b.pk]))
                self.assertEqual(resp.status_code, 404)
                self.assert_no_leak(resp)
        # SEC-REQ-4 wants 404 here; students currently answers 403 (docs/SECURITY_AUDIT.md, problem S-1).
        for name in ("students:profile_detail", "students:profile_edit"):
            with self.subTest(route=name):
                resp = self.client.get(reverse(name, args=[self.b.pk]))
                self.assertIn(resp.status_code, (403, 404))
                self.assert_no_leak(resp)

    def test_tc20_boys_warden_cannot_open_girls_application(self):
        self.client.login(email="warden.boys@hms.local", password=PASSWORD)
        with self.assertLogs("hms.security", level="WARNING") as logs:
            resp = self.client.get(reverse("allocation:allocate", args=[self.girl_application.pk]))
        self.assertEqual(resp.status_code, 404)
        self.assertNotIn(b"Gita Nair", resp.content)
        self.assertEqual(logs.records[0].security_event, "not_found")
        self.assertEqual(logs.records[0].user_id, self.warden_boys.pk)
        resp = self.client.post(reverse("allocation:reject", args=[self.girl_application.pk]),
                                {"reason": "Trying another hostel's student."})
        self.assertEqual(resp.status_code, 404)
        self.girl_application.refresh_from_db()
        self.assertEqual(self.girl_application.status, "PENDING")


class SecurityLoggingTests(TestCase):
    def test_tc20_scope_exceptions_become_403_404_and_tokens_are_redacted(self):
        from django.core.exceptions import PermissionDenied
        from django.http import Http404

        from apps.core.exceptions import AccessDenied, ObjectNotFound
        from apps.core.permissions import role_required

        admin = User.objects.create_user("admin@hms.local", PASSWORD, role=Role.ADMIN)
        request = RequestFactory().get("/accounts/verify/abc123token/")
        request.user = admin
        request.resolver_match = type("Match", (), {"kwargs": {"token": "abc123token"}})()

        for raised, expected in ((AccessDenied, PermissionDenied), (ObjectNotFound, Http404)):
            @role_required(Role.ADMIN)
            def view(req, token):
                raise raised()

            with self.subTest(raised=raised.__name__):
                with self.assertLogs("hms.security", level="WARNING") as logs, self.assertRaises(expected):
                    view(request, token="abc123token")
                self.assertNotIn("abc123token", logs.output[0])
                self.assertIn("/accounts/verify/<redacted>/", logs.output[0])

    def test_tc20_view_returning_403_is_logged(self):
        from django.http import HttpResponse

        from apps.core.permissions import role_required

        @role_required(Role.ADMIN)
        def view(req):
            return HttpResponse("Forbidden", status=403)

        request = RequestFactory().get("/fees/payments/RCP-2026-00001/receipt.pdf")
        request.user = User.objects.create_user("admin@hms.local", PASSWORD, role=Role.ADMIN)
        with self.assertLogs("hms.security", level="WARNING") as logs:
            self.assertEqual(view(request).status_code, 403)
        self.assertEqual(logs.records[0].security_event, "forbidden")
