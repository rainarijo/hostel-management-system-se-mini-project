"""Tests for enqueue(): Pending row, idempotent, part of the caller's transaction (SAD 4.2.2)."""
from django.db import transaction
from django.test import TestCase

from apps.notifications.models import NotificationOutbox, OutboxStatus
from apps.notifications.services import APPLICATION_ALLOCATED, enqueue


class EnqueueTests(TestCase):
    def test_enqueue_creates_pending_row(self):
        row = enqueue(APPLICATION_ALLOCATED, "a@hms.local", 5, {"room": "101"})
        self.assertEqual(row.status, OutboxStatus.PENDING)
        self.assertEqual((row.kind, row.entity_id, row.payload), (APPLICATION_ALLOCATED, "5", {"room": "101"}))

    def test_duplicate_enqueue_creates_no_second_row(self):
        first = enqueue(APPLICATION_ALLOCATED, "a@hms.local", 5, {"room": "101"})
        second = enqueue(APPLICATION_ALLOCATED, "a@hms.local", 5, {"room": "999"})
        self.assertEqual(first.pk, second.pk)
        self.assertEqual(NotificationOutbox.objects.count(), 1)

    def test_rollback_in_caller_leaves_no_row(self):
        with self.assertRaises(RuntimeError), transaction.atomic():
            enqueue(APPLICATION_ALLOCATED, "a@hms.local", 5, {})
            raise RuntimeError("business change failed")
        self.assertFalse(NotificationOutbox.objects.exists())
