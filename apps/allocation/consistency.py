"""NFR-REL-1: nightly consistency check (SAD 4.1.7). Read-only: it reports, it never fixes."""
from django.db.models import Count, Q

from apps.rooms.models import Room, RoomStatus

from .models import ACTIVE_STATUSES, Allocation


def _double_booked_rows():
    # order_by() clears Allocation's default ordering, which would otherwise be added to the GROUP BY.
    return (Allocation.objects.active().order_by().values("room", "bed_no")
            .annotate(n=Count("id")).filter(n__gt=1))


def _expected_status(room, occupied):
    """Same rule as Room.refresh_status, without saving."""
    return RoomStatus.FULL if occupied >= room.capacity else RoomStatus.AVAILABLE


def find_inconsistencies():
    """Return (double_booked_beds, status_mismatches).

    double_booked_beds: [(room, bed_no, count)] for beds held by more than one active allocation.
    status_mismatches: [(room, stored_status, expected_status)]. Rooms Under Maintenance are never a mismatch.
    """
    rows = list(_double_booked_rows())
    rooms = Room.objects.in_bulk({row["room"] for row in rows})
    double_booked = [(rooms.get(row["room"]), row["bed_no"], row["n"]) for row in rows]

    mismatches = []
    counted = (Room.objects.exclude(status=RoomStatus.MAINTENANCE).select_related("hostel")
               .annotate(occupied=Count("allocations", filter=Q(allocations__status__in=ACTIVE_STATUSES))))
    for room in counted:
        expected = _expected_status(room, room.occupied)
        if room.status != expected:
            mismatches.append((room, room.status, expected))
    return double_booked, mismatches
