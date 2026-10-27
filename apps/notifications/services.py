"""Notification queueing (SAD 4.2.2). Business services enqueue; the dispatcher (issue #30) sends.

Never send e-mail directly from a feature: call enqueue() inside the same transaction as the business change,
so a rollback also removes the message.
"""
from .models import NotificationOutbox, OutboxStatus

# FR-9.1: one kind per e-mail. Use these names everywhere.
ACCOUNT_VERIFICATION = "ACCOUNT_VERIFICATION"
PASSWORD_RESET = "PASSWORD_RESET"
APPLICATION_RECEIVED = "APPLICATION_RECEIVED"
APPLICATION_ALLOCATED = "APPLICATION_ALLOCATED"
APPLICATION_REJECTED = "APPLICATION_REJECTED"
ROOM_CHANGE_APPROVED = "ROOM_CHANGE_APPROVED"
ROOM_CHANGE_REJECTED = "ROOM_CHANGE_REJECTED"
COMPLAINT_STATUS_CHANGED = "COMPLAINT_STATUS_CHANGED"


def enqueue(kind, recipient_email, entity_id, payload):
    """Queue one e-mail as a Pending outbox row and return it. A duplicate (same kind, entity, recipient) is ignored.

    Runs in the caller's transaction; it does not open one of its own.
    """
    row, _ = NotificationOutbox.objects.get_or_create(
        kind=kind, entity_id=str(entity_id), recipient_email=recipient_email,
        defaults={"payload": payload or {}, "status": OutboxStatus.PENDING},
    )
    return row
