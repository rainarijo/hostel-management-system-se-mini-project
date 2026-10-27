from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.core.models import AuditLog


class Command(BaseCommand):
    help = "Purge audit log entries older than one year."

    def handle(self, *args, **options):
        cutoff = timezone.now() - timedelta(days=365)
        expired = AuditLog.objects.filter(timestamp__lt=cutoff)

        deleted_count, _ = expired.purge_expired()

        self.stdout.write(
            self.style.SUCCESS(
                f"Purged {deleted_count} expired audit log record(s)."
            )
        )
