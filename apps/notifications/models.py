from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.core.models import TimeStampedModel
from apps.rooms.models import Hostel


class AnnouncementQuerySet(models.QuerySet):
    def current(self):
        return self.filter(expiry_date__gte=timezone.localdate())


class Announcement(TimeStampedModel):
    """FR-9.3."""
    hostel = models.ForeignKey(Hostel, on_delete=models.CASCADE, related_name="announcements")
    title = models.CharField(max_length=100)
    body = models.TextField(max_length=2000)
    expiry_date = models.DateField()
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)

    objects = AnnouncementQuerySet.as_manager()

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.title


class EmailLog(TimeStampedModel):
    """FR-9.2: record of every notification e-mail and its retries."""
    to_email = models.EmailField()
    subject = models.CharField(max_length=200)
    event = models.CharField(max_length=50)
    attempts = models.PositiveSmallIntegerField(default=0)
    sent = models.BooleanField(default=False)
    last_error = models.TextField(blank=True)

    def __str__(self):
        return f"{self.event} to {self.to_email}"


class OutboxStatus(models.TextChoices):
    PENDING = "PENDING", "Pending"
    SENT = "SENT", "Sent"
    FAILED = "FAILED", "Failed"


class NotificationOutbox(TimeStampedModel):
    """Mail queue (SAD 4.1.7). Rows are written in the same transaction as the business change
    and sent later by the send_pending_notifications command. FR-4.10, FR-9.1, FR-9.2."""
    kind = models.CharField(max_length=40)          # e.g. ACCOUNT_VERIFICATION, APPLICATION_ALLOCATED
    recipient_email = models.EmailField()
    entity_id = models.CharField(max_length=40, blank=True)
    payload = models.JSONField(default=dict, blank=True)
    status = models.CharField(max_length=7, choices=OutboxStatus.choices, default=OutboxStatus.PENDING)
    attempts = models.PositiveSmallIntegerField(default=0)
    next_attempt_at = models.DateTimeField(default=timezone.now)
    last_error = models.TextField(blank=True)

    class Meta:
        constraints = [  # makes enqueueing idempotent
            models.UniqueConstraint(fields=["kind", "entity_id", "recipient_email"], name="uniq_outbox_message"),
        ]

    def __str__(self):
        return f"{self.kind} to {self.recipient_email} ({self.get_status_display()})"
