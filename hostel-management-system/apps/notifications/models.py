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
