"""TC-16: notification delivery, retry and final-failure behaviour."""
from datetime import timedelta
from unittest.mock import patch

from django.core import mail
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from apps.core.models import AuditLog

from apps.notifications.models import EmailLog, NotificationOutbox, OutboxStatus
from apps.notifications.services import APPLICATION_ALLOCATED, enqueue


class NotificationDispatcherTests(TestCase):
    def test_pending_notification_is_sent_as_plain_text_and_html(self):
        row = enqueue(
            APPLICATION_ALLOCATED,
            "student@hms.local",
            {
                "entity_id": "APP-2026-00001",
                "name": "Student One",
                "application_no": "APP-2026-00001",
                "hostel": "Boys Hostel",
                "room": "101",
                "bed": 2,
                "status": "Provisional",
            },
        )

        call_command("send_pending_notifications")

        row.refresh_from_db()
        self.assertEqual(row.status, OutboxStatus.SENT)
        self.assertEqual(row.attempts, 1)
        self.assertEqual(len(mail.outbox), 1)
        message = mail.outbox[0]
        self.assertIn("APP-2026-00001", message.body)
        self.assertEqual(len(message.alternatives), 1)
        self.assertEqual(message.alternatives[0][1], "text/html")
        self.assertTrue(EmailLog.objects.get().sent)

    @patch("apps.notifications.management.commands.send_pending_notifications.EmailMultiAlternatives.send")
    def test_tc16_failed_mail_retried_three_times(self, send):
        send.side_effect = RuntimeError("SMTP unavailable")
        row = NotificationOutbox.objects.create(
            kind=APPLICATION_ALLOCATED,
            recipient_email="student@hms.local",
            entity_id="APP-2026-00002",
            payload={
                "entity_id": "APP-2026-00002",
                "name": "Student Two",
                "application_no": "APP-2026-00002",
                "hostel": "Boys Hostel",
                "room": "102",
                "bed": 1,
                "status": "Provisional",
            },
        )

        for _ in range(4):
            call_command("send_pending_notifications")
            row.refresh_from_db()
            if row.status == OutboxStatus.FAILED:
                break
            row.next_attempt_at = timezone.now() - timedelta(seconds=1)
            row.save(update_fields=["next_attempt_at", "updated_at"])

        row.refresh_from_db()
        self.assertEqual(send.call_count, 4)
        self.assertEqual(row.attempts, 4)
        self.assertEqual(row.status, OutboxStatus.FAILED)
        self.assertEqual(EmailLog.objects.filter(sent=False).count(), 4)
        self.assertEqual(
            AuditLog.objects.filter(action="NOTIFICATION_DELIVERY_FAILED").count(),
            1,
        )

    @patch("apps.notifications.management.commands.send_pending_notifications.EmailMultiAlternatives.send")
    def test_failed_mail_waits_five_minutes_before_retry(self, send):
        send.side_effect = RuntimeError("SMTP unavailable")
        row = NotificationOutbox.objects.create(
            kind=APPLICATION_ALLOCATED,
            recipient_email="student@hms.local",
            entity_id="APP-2026-00003",
            payload={"entity_id": "APP-2026-00003", "name": "Student Three"},
        )

        call_command("send_pending_notifications")
        row.refresh_from_db()

        self.assertEqual(row.status, OutboxStatus.PENDING)
        self.assertEqual(row.attempts, 1)
        self.assertGreaterEqual(
            row.next_attempt_at,
            timezone.now() + timedelta(minutes=4, seconds=55),
        )
        self.assertEqual(send.call_count, 1)

    def test_unknown_notification_kind_is_rejected(self):
        with self.assertRaises(ValueError):
            enqueue("NOT_A_REAL_KIND", "student@hms.local", {"entity_id": "1"})
