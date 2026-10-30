"""Tests for NFR-REL-1 nightly consistency check, and the NFR-SAFE-1 ops files."""
from io import StringIO
from pathlib import Path
from unittest import mock

from django.conf import settings
from django.core import mail
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from apps.accounts.models import Role, User
from apps.allocation.models import Allocation
from apps.rooms.models import Hostel, Room, RoomStatus
from apps.students.models import StudentProfile

PASSWORD = "Strongpass2026"
OK = "OK: 0 double-booked beds, 0 room status mismatches"


class ConsistencyCheckTests(TestCase):
    def setUp(self):
        self.hostel = Hostel.objects.create(name="Cauvery Block", gender_type="M")
        self.room = Room.objects.create(hostel=self.hostel, room_no="101", floor=1, room_type="DOUBLE", capacity=2,
                                        annual_fee=80000)
        User.objects.create_user("admin@hms.local", PASSWORD, role=Role.ADMIN)
        User.objects.create_user("old-admin@hms.local", PASSWORD, role=Role.ADMIN, is_active=False)
        User.objects.create_user("wb@hms.local", PASSWORD, role=Role.WARDEN)

    def run_check(self, *args):
        out = StringIO()
        try:
            call_command("nightly_consistency_check", *args, stdout=out)
        except SystemExit as exc:
            return exc.code, out.getvalue()
        return 0, out.getvalue()

    def test_nfr_rel1_clean_database_reports_ok(self):
        user = User.objects.create_user("s1@hms.local", PASSWORD, role=Role.STUDENT)
        student = StudentProfile.objects.create(user=user, srn="PES1UG24CS001", name="Student 1", gender="M",
                                                program="B.Tech CSE", year=1)
        Allocation.objects.create(student=student, room=self.room, bed_no=1, start_date=timezone.localdate())
        code, out = self.run_check()
        self.assertEqual(code, 0)
        self.assertIn(OK, out)
        self.assertEqual(len(mail.outbox), 0)

    def test_nfr_rel1_detects_room_status_mismatch(self):
        Room.objects.filter(pk=self.room.pk).update(status=RoomStatus.FULL)      # empty room stored as Full
        with self.assertLogs("hms.consistency", level="ERROR"):
            code, out = self.run_check()
        self.assertEqual(code, 1)
        self.assertIn(f"STATUS MISMATCH: {self.room} is stored as FULL, expected AVAILABLE", out)

    def test_nfr_rel1_maintenance_room_not_a_mismatch(self):
        Room.objects.filter(pk=self.room.pk).update(status=RoomStatus.MAINTENANCE)
        code, out = self.run_check()
        self.assertEqual(code, 0)
        self.assertIn(OK, out)

    def test_nfr_rel1_detects_double_booked_bed(self):
        # uniq_active_bed makes this impossible to create, so the query result is faked.
        rows = [{"room": self.room.pk, "bed_no": 1, "n": 2}]
        with mock.patch("apps.allocation.consistency._double_booked_rows", return_value=rows):
            with self.assertLogs("hms.consistency", level="ERROR"):
                code, out = self.run_check("--no-email")
        self.assertEqual(code, 1)
        self.assertIn(f"DOUBLE-BOOKED: {self.room} bed 1 has 2 active allocations", out)

    def test_nfr_rel1_admins_notified_on_finding(self):
        Room.objects.filter(pk=self.room.pk).update(status=RoomStatus.FULL)
        with self.assertLogs("hms.consistency", level="ERROR"):
            code, _ = self.run_check()
        self.assertEqual(code, 1)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["admin@hms.local"])           # active Administrators only
        self.assertIn("1 room status mismatches", mail.outbox[0].subject)
        self.assertIn(str(self.room), mail.outbox[0].body)

    def test_nfr_rel1_no_email_flag_sends_nothing(self):
        Room.objects.filter(pk=self.room.pk).update(status=RoomStatus.FULL)
        with self.assertLogs("hms.consistency", level="ERROR"):
            code, _ = self.run_check("--no-email")
        self.assertEqual(code, 1)
        self.assertEqual(len(mail.outbox), 0)


class OpsFilesTests(TestCase):
    def test_nfr_safe1_ops_files_present(self):
        ops = Path(settings.BASE_DIR) / "ops"
        for name in ("backup.sh", "restore_test.sh", "systemd/hms-consistency.timer", "systemd/hms-backup.timer",
                     "systemd/hms-restore-test.timer"):
            self.assertTrue((ops / name).is_file(), name)
        backup_timer = (ops / "systemd/hms-backup.timer").read_text()
        self.assertIn("02:00:00", backup_timer)
        self.assertIn("Asia/Kolkata", backup_timer)
        backup = (ops / "backup.sh").read_text()
        self.assertIn("-mtime +30", backup)
        self.assertIn("set -euo pipefail", backup)
        self.assertNotIn("PGPASSWORD", backup)
