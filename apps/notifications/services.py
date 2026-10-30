"""Notification queueing and message rendering for FR-9.1/FR-9.2.

Business services enqueue notifications inside their existing transactions. The
management command is responsible for delivery and retries.
"""
from django.conf import settings
from django.template.loader import render_to_string

from .models import NotificationOutbox, OutboxStatus

# FR-9.1. The issue text says "seven" kinds, but its acceptance list contains
# eight distinct notifications. Keep all eight explicitly represented.
ACCOUNT_VERIFICATION = "ACCOUNT_VERIFICATION"
PASSWORD_RESET = "PASSWORD_RESET"
APPLICATION_RECEIVED = "APPLICATION_RECEIVED"
APPLICATION_ALLOCATED = "APPLICATION_ALLOCATED"
APPLICATION_REJECTED = "APPLICATION_REJECTED"
ROOM_CHANGE_APPROVED = "ROOM_CHANGE_APPROVED"
ROOM_CHANGE_REJECTED = "ROOM_CHANGE_REJECTED"
COMPLAINT_STATUS_CHANGED = "COMPLAINT_STATUS_CHANGED"

MESSAGE_KINDS = (
    ACCOUNT_VERIFICATION,
    PASSWORD_RESET,
    APPLICATION_RECEIVED,
    APPLICATION_ALLOCATED,
    APPLICATION_REJECTED,
    ROOM_CHANGE_APPROVED,
    ROOM_CHANGE_REJECTED,
    COMPLAINT_STATUS_CHANGED,
)

MESSAGE_DEFINITIONS = {
    ACCOUNT_VERIFICATION: {
        "subject": "Verify your Hostel Management System account",
        "template": "notifications/account_verification",
    },
    PASSWORD_RESET: {
        "subject": "Reset your Hostel Management System password",
        "template": "notifications/password_reset",
    },
    APPLICATION_RECEIVED: {
        "subject": "Hostel room application received",
        "template": "notifications/application_received",
    },
    APPLICATION_ALLOCATED: {
        "subject": "Hostel room application allocated",
        "template": "notifications/application_allocated",
    },
    APPLICATION_REJECTED: {
        "subject": "Hostel room application rejected",
        "template": "notifications/application_rejected",
    },
    ROOM_CHANGE_APPROVED: {
        "subject": "Hostel room change approved",
        "template": "notifications/room_change_approved",
    },
    ROOM_CHANGE_REJECTED: {
        "subject": "Hostel room change rejected",
        "template": "notifications/room_change_rejected",
    },
    COMPLAINT_STATUS_CHANGED: {
        "subject": "Hostel complaint status updated",
        "template": "notifications/complaint_status_changed",
    },
}


def enqueue(kind, recipient_email, payload, legacy_payload=None):
    """Queue one e-mail idempotently and return the outbox row.

    The public Issue #30 form is:
        enqueue(kind, recipient_email, payload)

    The payload must contain ``entity_id``. For compatibility with existing
    Sprint-1 tests/callers, the old four-argument form is also accepted:
        enqueue(kind, recipient_email, entity_id, payload)

    In the legacy form, ``entity_id`` is stored in the dedicated database
    column and the supplied payload is preserved unchanged.
    """
    if kind not in MESSAGE_DEFINITIONS:
        raise ValueError(f"Unsupported notification kind: {kind}")

    if legacy_payload is not None:
        entity_id = str(payload)
        payload = dict(legacy_payload or {})
    else:
        payload = dict(payload or {})
        if "entity_id" not in payload:
            raise ValueError("Notification payload must contain entity_id")
        entity_id = str(payload["entity_id"])

    row, _ = NotificationOutbox.objects.get_or_create(
        kind=kind,
        entity_id=entity_id,
        recipient_email=recipient_email,
        defaults={
            "payload": payload,
            "status": OutboxStatus.PENDING,
        },
    )
    return row


def render_notification(row):
    """Return (subject, plain_text, html) for an outbox row."""
    definition = MESSAGE_DEFINITIONS.get(row.kind)
    if definition is None:
        raise ValueError(f"Unsupported notification kind: {row.kind}")

    context = dict(row.payload or {})
    context.setdefault("recipient_email", row.recipient_email)
    context.setdefault("default_from_email", settings.DEFAULT_FROM_EMAIL)
    template = definition["template"]
    text = render_to_string(f"{template}.txt", context).strip()
    html = render_to_string(f"{template}.html", context).strip()
    return definition["subject"], text, html
