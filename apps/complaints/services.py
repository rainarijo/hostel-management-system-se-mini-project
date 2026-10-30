"""Complaint business rules for FR-6.3, FR-6.4 and FR-6.5."""
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from apps.allocation.models import Allocation
from apps.core.audit import log_action
from apps.notifications.services import COMPLAINT_STATUS_CHANGED, enqueue

from .models import Complaint, ComplaintStatus


class NoActiveAllocation(Exception):
    """FR-6.1: only a student with an active allocation may raise a complaint."""


class InvalidComplaintTransition(Exception):
    """Raised when a requested complaint status transition is not permitted."""


class ReopenWindowExpired(Exception):
    """Raised when a resolved complaint is reopened after the 7-day window."""


ALLOWED_STATUS_TRANSITIONS = {
    ComplaintStatus.OPEN: {
        ComplaintStatus.IN_PROGRESS,
        ComplaintStatus.REJECTED,
    },
    ComplaintStatus.IN_PROGRESS: {
        ComplaintStatus.RESOLVED,
        ComplaintStatus.REJECTED,
    },
}


@transaction.atomic
def raise_complaint(user, student, category, description, request=None):
    """Create an Open complaint for the student's current room."""
    allocation = (
        Allocation.objects.active()
        .filter(student=student)
        .select_related("room__hostel")
        .first()
    )
    if allocation is None:
        raise NoActiveAllocation(
            "You can raise a complaint only while you have an active room allocation."
        )

    complaint = Complaint.objects.create(
        student=student,
        room=allocation.room,
        category=category,
        description=description,
    )
    log_action(
        "COMPLAINT_RAISED",
        user=user,
        entity="complaint",
        entity_id=complaint.complaint_no,
        new=category,
        request=request,
    )
    return complaint


@transaction.atomic
def change_status(complaint, new_status, remark, user, request=None):
    """Apply one permitted Warden status transition.

    Every status change requires a non-empty remark. Resolution records the
    resolution timestamp; reopening clears it in the separate reopen flow.
    """
    new_status = str(new_status)
    remark = (remark or "").strip()

    if not remark:
        raise InvalidComplaintTransition("A remark is required for every status change.")

    allowed = ALLOWED_STATUS_TRANSITIONS.get(complaint.status, set())
    if new_status not in allowed:
        raise InvalidComplaintTransition(
            f"Cannot change complaint {complaint.complaint_no} "
            f"from {complaint.get_status_display()} to {new_status}."
        )

    old_status = complaint.status
    complaint.status = new_status
    complaint.remark = remark
    if new_status == ComplaintStatus.RESOLVED:
        complaint.resolved_at = timezone.now()
    else:
        complaint.resolved_at = None
    complaint.save(update_fields=["status", "remark", "resolved_at", "updated_at"])

    log_action(
        "COMPLAINT_STATUS_CHANGED",
        user=user,
        entity="complaint",
        entity_id=complaint.complaint_no,
        old=old_status,
        new=new_status,
        request=request,
    )

    enqueue(
        COMPLAINT_STATUS_CHANGED,
        complaint.student.user.email,
        {
            "entity_id": complaint.complaint_no,
            "name": complaint.student.name,
            "complaint_no": complaint.complaint_no,
            "old_status": old_status,
            "new_status": new_status,
            "remark": remark,
        },
    )

    return complaint


@transaction.atomic
def reopen_complaint(complaint, user, request=None):
    """Reopen a Resolved complaint within seven days and return it to Open."""
    if complaint.status != ComplaintStatus.RESOLVED:
        raise InvalidComplaintTransition(
            "Only a resolved complaint can be reopened."
        )

    if complaint.resolved_at is None:
        raise InvalidComplaintTransition(
            "The complaint has no recorded resolution time."
        )

    if timezone.now() > complaint.resolved_at + timedelta(days=7):
        raise ReopenWindowExpired(
            "A resolved complaint can be reopened only within 7 days of resolution."
        )

    old_status = complaint.status
    complaint.status = ComplaintStatus.OPEN
    complaint.resolved_at = None
    complaint.save(update_fields=["status", "resolved_at", "updated_at"])

    log_action(
        "COMPLAINT_REOPENED",
        user=user,
        entity="complaint",
        entity_id=complaint.complaint_no,
        old=old_status,
        new=ComplaintStatus.OPEN,
        request=request,
    )

    return complaint


def overdue_complaints(queryset=None, now=None):
    """Return Open/In Progress complaints older than 72 hours."""
    if queryset is None:
        queryset = Complaint.objects.all()

    now = now or timezone.now()
    cutoff = now - timedelta(hours=72)
    return queryset.filter(
        status__in=[ComplaintStatus.OPEN, ComplaintStatus.IN_PROGRESS],
        created_at__lt=cutoff,
    )
