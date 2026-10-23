from django.core.exceptions import ValidationError

from apps.allocation.models import ACTIVE_STATUSES, Allocation
from apps.rooms.models import RoomStatus


def validate_allocation_room(room, allocation=None, status=None, bed_no=None):
    status = status or getattr(allocation, "status", None)
    if status not in ACTIVE_STATUSES:
        return

    if room.status == RoomStatus.MAINTENANCE:
        raise ValidationError("Room is under maintenance.")
    if not room.is_active:
        raise ValidationError("Cannot allocate to an inactive room.")
    if not room.hostel.is_active:
        raise ValidationError("Cannot allocate to an inactive hostel.")
    if bed_no is not None and not 1 <= bed_no <= room.capacity:
        raise ValidationError(f"Bed number must be within the room capacity (1-{room.capacity}).")

    occupied = Allocation.objects.active().filter(room_id=room.pk)
    if allocation is not None and allocation.pk:
        occupied = occupied.exclude(pk=allocation.pk)
    if occupied.count() >= room.capacity:
        raise ValidationError("There are no vacant beds in the room.")
