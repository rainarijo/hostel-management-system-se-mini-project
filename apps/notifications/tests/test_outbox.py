"""Outbox enqueueing is idempotent (SAD 4.4.2)."""
from django.db import IntegrityError, transaction
from django.test import TestCase

from apps.notifications.models import NotificationOutbox


class OutboxTests(TestCase):
    def test_same_message_cannot_be_queued_twice(self):
        msg = dict(kind="APPLICATION_ALLOCATED", recipient_email="a@hms.local", entity_id="5")
        NotificationOutbox.objects.create(**msg)
        with self.assertRaises(IntegrityError), transaction.atomic():
            NotificationOutbox.objects.create(**msg)

    def test_same_kind_for_another_entity_is_allowed(self):
        NotificationOutbox.objects.create(kind="APPLICATION_ALLOCATED", recipient_email="a@hms.local", entity_id="5")
        NotificationOutbox.objects.create(kind="APPLICATION_ALLOCATED", recipient_email="a@hms.local", entity_id="6")
        self.assertEqual(NotificationOutbox.objects.count(), 2)
