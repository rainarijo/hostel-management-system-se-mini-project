from django.contrib import messages
from django.db import IntegrityError, transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.accounts.models import Role
from apps.core.audit import log_action
from apps.core.permissions import role_required

from .forms import HostelForm, RoomForm
from .models import Hostel, Room


def _save_form_or_add_error(form, error):
    try:
        with transaction.atomic():
            return form.save()
    except IntegrityError:
        form.add_error(None, error)
        return None


@role_required(Role.WARDEN, Role.ADMIN)
def index(request):
    if request.user.role == Role.ADMIN:
        hostels = Hostel.objects.all()
        rooms = Room.objects.select_related("hostel").all()
    else:
        hostels = Hostel.objects.filter(wardens=request.user)
        rooms = Room.objects.select_related("hostel").filter(hostel__wardens=request.user)
    return render(request, "rooms/index.html", {"hostels": hostels.distinct(), "rooms": rooms})


def _hostel_audit_value(hostel):
    wardens = ", ".join(hostel.wardens.order_by("email").values_list("email", flat=True))
    return (
        f"Name: {hostel.name}; gender: {hostel.get_gender_type_display()}; "
        f"wardens: {wardens}; active: {hostel.is_active}"
    )


def _room_audit_value(room):
    return (
        f"Hostel: {room.hostel.name}; room: {room.room_no}; floor: {room.floor}; "
        f"type: {room.get_room_type_display()}; capacity: {room.capacity}; "
        f"annual fee: {room.annual_fee}; status: {room.get_status_display()}"
    )


@role_required(Role.ADMIN)
def hostel_create(request):
    form = HostelForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        hostel = _save_form_or_add_error(form, "A hostel with this name already exists. Choose a different name.")
        if hostel is not None:
            log_action("HOSTEL_CREATED", user=request.user, entity="hostel", entity_id=hostel.pk,
                       new=_hostel_audit_value(hostel), request=request)
            messages.success(request, f"Hostel {hostel.name} created.")
            return redirect("rooms:index")
    return render(request, "rooms/hostel_form.html", {"form": form, "is_new": True})


@role_required(Role.ADMIN)
def hostel_edit(request, pk):
    hostel = get_object_or_404(Hostel, pk=pk)
    old = _hostel_audit_value(hostel)
    form = HostelForm(request.POST or None, instance=hostel)
    if request.method == "POST" and form.is_valid():
        updated_hostel = _save_form_or_add_error(
            form, "A hostel with this name already exists. Choose a different name.")
        if updated_hostel is not None:
            hostel = updated_hostel
            log_action("HOSTEL_UPDATED", user=request.user, entity="hostel", entity_id=hostel.pk,
                       old=old, new=_hostel_audit_value(hostel), request=request)
            messages.success(request, f"Hostel {hostel.name} updated.")
            return redirect("rooms:index")
    return render(request, "rooms/hostel_form.html", {"form": form, "is_new": False, "hostel": hostel})


@role_required(Role.ADMIN)
@require_POST
def hostel_deactivate(request, pk):
    hostel = get_object_or_404(Hostel, pk=pk)
    if hostel.is_active:
        old = _hostel_audit_value(hostel)
        hostel.is_active = False
        hostel.save(update_fields=["is_active", "updated_at"])
        log_action("HOSTEL_DEACTIVATED", user=request.user, entity="hostel", entity_id=hostel.pk,
                   old=old, new=_hostel_audit_value(hostel), request=request)
        messages.success(request, f"Hostel {hostel.name} deactivated.")
    else:
        messages.info(request, f"Hostel {hostel.name} is already inactive.")
    return redirect("rooms:index")


@role_required(Role.ADMIN)
def room_create(request):
    form = RoomForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        room = _save_form_or_add_error(
            form, "That room conflicts with an existing room or a database constraint. "
                  "Review the values and try again.")
        if room is not None:
            log_action("ROOM_CREATED", user=request.user, entity="room", entity_id=room.pk,
                       new=_room_audit_value(room), request=request)
            messages.success(request, f"Room {room.room_no} created.")
            return redirect("rooms:index")
    return render(request, "rooms/room_form.html", {"form": form, "is_new": True})


@role_required(Role.ADMIN)
def room_edit(request, pk):
    room = get_object_or_404(Room.objects.select_related("hostel"), pk=pk)
    old = _room_audit_value(room)
    form = RoomForm(request.POST or None, instance=room)
    if request.method == "POST" and form.is_valid():
        updated_room = _save_form_or_add_error(
            form, "That room conflicts with an existing room or a database constraint. "
                  "Review the values and try again.")
        if updated_room is not None:
            room = updated_room
            log_action("ROOM_UPDATED", user=request.user, entity="room", entity_id=room.pk,
                       old=old, new=_room_audit_value(room), request=request)
            messages.success(request, f"Room {room.room_no} updated.")
            return redirect("rooms:index")
    return render(request, "rooms/room_form.html", {"form": form, "is_new": False, "room": room})
