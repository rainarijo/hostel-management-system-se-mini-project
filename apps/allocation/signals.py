
"""Keep allocation validation and room status synchronized."""

from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from apps.rooms.models import Room

from .models import ACTIVE_STATUSES, Allocation
from .services import validate_allocation_room


@receiver(
    pre_save,
    sender=Allocation,
    dispatch_uid="allocation_validate_room",
)
def validate_room_for_active_allocation(sender, instance, **kwargs):
    if instance.status in ACTIVE_STATUSES:
        validate_allocation_room(
            instance.room,
            allocation=instance,
            status=instance.status,
            bed_no=instance.bed_no,
        )


@receiver(
    pre_save,
    sender=Allocation,
    dispatch_uid="allocation_remember_previous_room",
)
def remember_previous_room(sender, instance, **kwargs):
    instance._previous_room_id = None

    if instance.pk:
        instance._previous_room_id = (
            Allocation.objects.filter(pk=instance.pk)
            .values_list("room_id", flat=True)
            .first()
        )


@receiver(
    post_save,
    sender=Allocation,
    dispatch_uid="allocation_refresh_room_status",
)
def refresh_room_status_after_allocation_save(
    sender, instance, created=False, **kwargs
):
    room_ids = {
        instance.room_id,
        getattr(instance, "_previous_room_id", None),
    } - {None}

    for room in Room.objects.filter(pk__in=room_ids):
        room.refresh_status()
