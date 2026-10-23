from django.core.exceptions import ValidationError
from django.db.models.deletion import ProtectedError
from django.db.models.signals import post_save, pre_delete, pre_save
from django.dispatch import receiver

from apps.allocation.models import ACTIVE_STATUSES, Allocation

from .models import Hostel, Room, RoomStatus
from .validators import validate_allocation_room


@receiver(pre_save, sender=Allocation, dispatch_uid="rooms_validate_allocation")
def validate_active_allocation(sender, instance, update_fields=None, **kwargs):
    instance._rooms_previous_room_id = None
    instance._rooms_saved_room_id = instance.room_id
    status = instance.status
    bed_no = instance.bed_no
    if instance.pk:
        previous = Allocation.objects.filter(pk=instance.pk).values("room_id", "status", "bed_no").first()
        if previous is not None:
            instance._rooms_previous_room_id = previous["room_id"]
            if update_fields is not None:
                if "room" not in update_fields and "room_id" not in update_fields:
                    instance._rooms_saved_room_id = previous["room_id"]
                if "status" not in update_fields:
                    status = previous["status"]
                if "bed_no" not in update_fields:
                    bed_no = previous["bed_no"]

    if status in ACTIVE_STATUSES:
        room = Room.objects.select_related("hostel").get(pk=instance._rooms_saved_room_id)
        validate_allocation_room(
            room, allocation=instance, status=status, bed_no=bed_no)


@receiver(post_save, sender=Allocation, dispatch_uid="rooms_refresh_allocation_rooms")
def refresh_allocation_rooms(sender, instance, **kwargs):
    room_ids = {
        getattr(instance, "_rooms_saved_room_id", instance.room_id),
        getattr(instance, "_rooms_previous_room_id", None),
    } - {None}
    for room in Room.objects.filter(pk__in=room_ids):
        room.refresh_status()
    if hasattr(instance, "_rooms_previous_room_id"):
        del instance._rooms_previous_room_id
    if hasattr(instance, "_rooms_saved_room_id"):
        del instance._rooms_saved_room_id


@receiver(pre_save, sender=Room, dispatch_uid="rooms_prevent_occupied_room_deactivation")
def prevent_occupied_room_deactivation(sender, instance, update_fields=None, **kwargs):
    if not instance.pk or instance.is_active:
        return
    if update_fields is not None and "is_active" not in update_fields:
        return
    was_active = Room.objects.filter(pk=instance.pk, is_active=True).exists()
    if was_active and Allocation.objects.active().filter(room_id=instance.pk).exists():
        raise ValidationError("Room has active allocations")


@receiver(pre_save, sender=Hostel, dispatch_uid="rooms_prevent_occupied_hostel_deactivation")
def prevent_occupied_hostel_deactivation(sender, instance, update_fields=None, **kwargs):
    if not instance.pk or instance.is_active:
        return
    if update_fields is not None and "is_active" not in update_fields:
        return
    was_active = Hostel.objects.filter(pk=instance.pk, is_active=True).exists()
    if was_active and Allocation.objects.active().filter(room__hostel_id=instance.pk).exists():
        raise ValidationError("Hostel has active allocations")


@receiver(pre_delete, sender=Room, dispatch_uid="rooms_prevent_room_deletion")
def prevent_room_deletion(sender, instance, **kwargs):
    raise ProtectedError("Room records cannot be deleted; deactivate the room instead.", {instance})


@receiver(pre_delete, sender=Hostel, dispatch_uid="rooms_prevent_hostel_deletion")
def prevent_hostel_deletion(sender, instance, **kwargs):
    raise ProtectedError("Hostel records cannot be deleted; deactivate the hostel instead.", {instance})


@receiver(pre_save, sender=Room, dispatch_uid="rooms_validate_room_capacity")
def validate_room_capacity(sender, instance, **kwargs):
    if not instance.pk:
        return
    previous_capacity = Room.objects.filter(pk=instance.pk).values_list("capacity", flat=True).first()
    if (previous_capacity is not None and instance.capacity < previous_capacity
            and Allocation.objects.active().filter(room_id=instance.pk).count() > instance.capacity):
        raise ValidationError("Capacity cannot be lower than the room's active occupancy.")


@receiver(pre_save, sender=Room, dispatch_uid="rooms_keep_room_status_consistent")
def keep_room_status_consistent(sender, instance, update_fields=None, **kwargs):
    if update_fields is not None and "status" not in update_fields:
        return
    if instance.status == RoomStatus.MAINTENANCE:
        return
    occupancy = Allocation.objects.active().filter(room_id=instance.pk).count() if instance.pk else 0
    instance.status = RoomStatus.FULL if occupancy >= instance.capacity else RoomStatus.AVAILABLE
