"""Complaint business rules (SAD 4.1.1: views stay thin, rules live here)."""
from django.db import transaction

from apps.allocation.models import Allocation
from apps.core.audit import log_action

from .models import Complaint


class NoActiveAllocation(Exception):
    """FR-6.1: only a student with an active allocation may raise a complaint."""


@transaction.atomic
def raise_complaint(user, student, category, description, request=None):
    """Create an Open complaint for the student's current room and write the audit entry.

    The room (and through it the hostel) is copied from the active allocation (FR-6.2).
    """
    allocation = (Allocation.objects.active().filter(student=student)
                  .select_related("room__hostel").first())
    if allocation is None:
        raise NoActiveAllocation("You can raise a complaint only while you have an active room allocation.")
    complaint = Complaint.objects.create(
        student=student, room=allocation.room, category=category, description=description)
    log_action("COMPLAINT_RAISED", user=user, entity="complaint", entity_id=complaint.complaint_no,
               new=category, request=request)
    return complaint
