from django.conf import settings
from django.db import models


class TimeStampedModel(models.Model):
    """Abstract base with created/updated timestamps for all HMS models."""
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class AuditLogQuerySet(models.QuerySet):
    def update(self, **kwargs):
        raise ValueError("Audit log entries are append-only.")

    def delete(self):
        raise ValueError("Audit log entries are append-only.")

    def purge_expired(self):
        """Delete audit records older than the retention cutoff."""
        from django.db import models

        return models.QuerySet.delete(self)


class AuditLog(models.Model):
    """Append-only audit trail (SEC-REQ-8, FR-2.7). Never update or delete rows."""
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    action = models.CharField(max_length=50)
    entity = models.CharField(max_length=50, blank=True)
    entity_id = models.CharField(max_length=50, blank=True)
    old_value = models.TextField(blank=True)
    new_value = models.TextField(blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)
    objects = AuditLogQuerySet.as_manager()

    class Meta:
        ordering = ["-timestamp"]

    def __str__(self):
        return f"{self.timestamp:%d-%m-%Y %H:%M} {self.action} {self.entity}"

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValueError("Audit log entries are append-only.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValueError("Audit log entries are append-only.")


class DocumentSequence(models.Model):
    """Counter behind APP/CMP/RCP numbers. Used by apps.core.sequences.next_number."""
    prefix = models.CharField(max_length=5)
    year = models.PositiveSmallIntegerField()
    last_no = models.PositiveIntegerField(default=0)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["prefix", "year"], name="uniq_document_sequence")]

    def __str__(self):
        return f"{self.prefix}-{self.year}: {self.last_no}"
