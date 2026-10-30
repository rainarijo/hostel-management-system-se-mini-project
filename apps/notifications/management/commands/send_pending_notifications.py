"""Deliver queued notification e-mails and retry transient failures."""
from datetime import timedelta

from django.core.mail import EmailMultiAlternatives
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.core.audit import log_action

from ...models import EmailLog, NotificationOutbox, OutboxStatus
from ...services import render_notification

RETRY_DELAY = timedelta(minutes=5)
MAX_RETRIES = 3
MAX_ATTEMPTS = MAX_RETRIES + 1


class Command(BaseCommand):
    help = "Send pending notification e-mails and retry failures."

    def add_arguments(self, parser):
        parser.add_argument(
            "--limit",
            type=int,
            default=100,
            help="Maximum number of eligible outbox rows to process (default: 100).",
        )

    def handle(self, *args, **options):
        limit = max(options["limit"], 1)
        now = timezone.now()
        rows = list(
            NotificationOutbox.objects.filter(
                status=OutboxStatus.PENDING,
                next_attempt_at__lte=now,
            ).order_by("next_attempt_at", "created_at", "pk")[:limit]
        )

        sent = failed = retried = 0
        for row in rows:
            result = self._deliver(row.pk)
            if result == "sent":
                sent += 1
            elif result == "retry":
                retried += 1
            elif result == "failed":
                failed += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Processed {len(rows)} notification(s): "
                f"{sent} sent, {retried} scheduled for retry, {failed} permanently failed."
            )
        )

    def _deliver(self, row_id):
        with transaction.atomic():
            try:
                row = NotificationOutbox.objects.select_for_update().get(pk=row_id)
            except NotificationOutbox.DoesNotExist:
                return None

            if row.status != OutboxStatus.PENDING or row.next_attempt_at > timezone.now():
                return None

            subject, text_body, html_body = render_notification(row)
            attempt_no = row.attempts + 1
            try:
                message = EmailMultiAlternatives(
                    subject=subject,
                    body=text_body,
                    from_email=None,
                    to=[row.recipient_email],
                    headers={"Content-Type": "text/plain; charset=utf-8"},
                )
                message.attach_alternative(html_body, "text/html")
                message.send(fail_silently=False)
            except Exception as exc:  # SMTP/backend failure must enter retry state.
                row.attempts = attempt_no
                row.last_error = str(exc)[:4000]
                EmailLog.objects.create(
                    to_email=row.recipient_email,
                    subject=subject,
                    event=row.kind,
                    attempts=attempt_no,
                    sent=False,
                    last_error=row.last_error,
                )

                if attempt_no >= MAX_ATTEMPTS:
                    row.status = OutboxStatus.FAILED
                    row.save(update_fields=["attempts", "last_error", "status", "updated_at"])
                    log_action(
                        "NOTIFICATION_DELIVERY_FAILED",
                        entity="notification_outbox",
                        entity_id=row.pk,
                        new=f"{row.kind} to {row.recipient_email}; attempts={attempt_no}; error={row.last_error}",
                    )
                    return "failed"

                row.status = OutboxStatus.PENDING
                row.next_attempt_at = timezone.now() + RETRY_DELAY
                row.save(
                    update_fields=[
                        "attempts", "last_error", "status", "next_attempt_at", "updated_at"
                    ]
                )
                return "retry"

            row.attempts = attempt_no
            row.status = OutboxStatus.SENT
            row.last_error = ""
            row.save(update_fields=["attempts", "status", "last_error", "updated_at"])
            EmailLog.objects.create(
                to_email=row.recipient_email,
                subject=subject,
                event=row.kind,
                attempts=attempt_no,
                sent=True,
                last_error="",
            )
            return "sent"
