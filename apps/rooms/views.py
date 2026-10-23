from django.contrib import messages
from django.db import IntegrityError, transaction
from django.db.models import Count, Q
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from apps.accounts.models import Role
from apps.allocation.models import ACTIVE_STATUSES
from apps.core.audit import log_action
from apps.core.permissions import role_required
from apps.students.models import StudentProfile

from .forms import AvailabilityFilterForm, HostelForm, RoomCSVImportForm, RoomForm
from .importers import CSVImportError, import_rooms
from .models import Hostel, Room, RoomStatus, RoomType


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
        f"annual fee: {room.annual_fee}; status: {room.get_status_display()}; active: {room.is_active}"
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
@transaction.atomic
def hostel_deactivate(request, pk):
    from apps.allocation.models import Allocation

    hostel = get_object_or_404(Hostel.objects.select_for_update(), pk=pk)
    if hostel.is_active:
        room_ids = list(Room.objects.select_for_update().filter(hostel=hostel).values_list("pk", flat=True))
        if Allocation.objects.active().filter(room_id__in=room_ids).exists():
            messages.error(request, "Hostel has active allocations")
            return redirect("rooms:index")
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
@require_POST
@transaction.atomic
def hostel_reactivate(request, pk):
    hostel = get_object_or_404(Hostel.objects.select_for_update(), pk=pk)
    if not hostel.is_active:
        old = _hostel_audit_value(hostel)
        hostel.is_active = True
        hostel.save(update_fields=["is_active", "updated_at"])
        log_action("HOSTEL_REACTIVATED", user=request.user, entity="hostel", entity_id=hostel.pk,
                   old=old, new=_hostel_audit_value(hostel), request=request)
        messages.success(request, f"Hostel {hostel.name} reactivated.")
    else:
        messages.info(request, f"Hostel {hostel.name} is already active.")
    return redirect("rooms:index")


@role_required(Role.ADMIN)
@require_POST
@transaction.atomic
def room_deactivate(request, pk):
    from apps.allocation.models import Allocation

    room = get_object_or_404(Room.objects.select_for_update(), pk=pk)
    if room.is_active:
        if Allocation.objects.active().filter(room=room).exists():
            messages.error(request, "Room has active allocations")
            return redirect("rooms:index")
        old = _room_audit_value(room)
        room.is_active = False
        room.save(update_fields=["is_active", "updated_at"])
        log_action("ROOM_DEACTIVATED", user=request.user, entity="room", entity_id=room.pk,
                   old=old, new=_room_audit_value(room), request=request)
        messages.success(request, f"Room {room.room_no} deactivated.")
    else:
        messages.info(request, f"Room {room.room_no} is already inactive.")
    return redirect("rooms:index")


@role_required(Role.ADMIN)
@require_POST
@transaction.atomic
def room_reactivate(request, pk):
    room = get_object_or_404(Room.objects.select_for_update(), pk=pk)
    if not room.is_active:
        old = _room_audit_value(room)
        room.is_active = True
        room.save(update_fields=["is_active", "updated_at"])
        log_action("ROOM_REACTIVATED", user=request.user, entity="room", entity_id=room.pk,
                   old=old, new=_room_audit_value(room), request=request)
        messages.success(request, f"Room {room.room_no} reactivated.")
    else:
        messages.info(request, f"Room {room.room_no} is already active.")
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


def _hostel_scope(user):
    if user.role == Role.ADMIN:
        return Hostel.objects.all()
    if user.role == Role.WARDEN:
        return user.hostels.filter(is_active=True)
    profile = StudentProfile.objects.filter(user=user).only("gender").first()
    if profile is None:
        return None
    return Hostel.objects.filter(is_active=True, gender_type=profile.gender)


def _availability_rooms(hostels, filters):
    rooms = (
        Room.objects.filter(hostel__in=hostels, hostel__is_active=True, is_active=True)
        .select_related("hostel")
        .annotate(occupied=Count("allocations", filter=Q(allocations__status__in=ACTIVE_STATUSES)))
    )
    if filters["hostel"] is not None:
        rooms = rooms.filter(hostel_id=filters["hostel"])
    if filters["floor"] is not None:
        rooms = rooms.filter(floor=filters["floor"])
    if filters["room_type"]:
        rooms = rooms.filter(room_type=filters["room_type"])
    return rooms


def _room_availability_data(rooms):
    return [
        {
            "room_id": room.pk,
            "hostel_id": room.hostel_id,
            "hostel_name": room.hostel.name,
            "room_no": room.room_no,
            "floor": room.floor,
            "room_type": room.get_room_type_display(),
            "capacity": room.capacity,
            "occupied": room.occupied,
            "vacant": max(room.capacity - room.occupied, 0),
            "status": room.get_status_display(),
        }
        for room in rooms
    ]


@role_required(Role.ADMIN, Role.WARDEN)
def availability_grid(request):
    form = AvailabilityFilterForm(request.GET if request.GET else None)
    rooms = Room.objects.none()
    hostels = _hostel_scope(request.user)
    if request.GET and form.is_valid():
        hostel_id = form.cleaned_data["hostel"]
        if hostel_id is not None and not hostels.filter(pk=hostel_id).exists():
            raise Http404
        rooms = _availability_rooms(hostels, form.cleaned_data)
    elif not request.GET:
        rooms = _availability_rooms(hostels, {"hostel": None, "floor": None, "room_type": ""})
    return render(request, "rooms/availability_grid.html", {
        "form": form,
        "hostels": hostels,
        "rooms": _room_availability_data(rooms),
    })


@require_GET
def availability_api(request):
    if not request.user.is_authenticated:
        return JsonResponse({"error": "UNAUTHENTICATED"}, status=401)
    if request.user.role not in (Role.ADMIN, Role.WARDEN, Role.STUDENT):
        log_action("ACCESS_DENIED", user=request.user, entity="url",
                   entity_id=request.path[:50], request=request)
        return JsonResponse({"error": "FORBIDDEN"}, status=403)

    allowed = {"hostel", "floor", "room_type"}
    if set(request.GET) - allowed:
        return JsonResponse({"error": "VALIDATION_ERROR", "message": "Unsupported filter."}, status=400)

    form = AvailabilityFilterForm(request.GET)
    if not form.is_valid():
        return JsonResponse({
            "error": "VALIDATION_ERROR",
            "fields": form.errors.get_json_data(),
        }, status=400)

    hostels = _hostel_scope(request.user)
    if hostels is None:
        return JsonResponse({"error": "FORBIDDEN", "message": "Student profile is required."}, status=403)

    hostel_id = form.cleaned_data["hostel"]
    if hostel_id is not None and not hostels.filter(pk=hostel_id).exists():
        return JsonResponse({"error": "NOT_FOUND"}, status=404)

    rooms = _availability_rooms(hostels, form.cleaned_data)
    if request.user.role == Role.STUDENT:
        vacancy_by_type = {room_type.label: 0 for room_type in RoomType}
        room_type_labels = dict(RoomType.choices)
        student_rooms = rooms.exclude(status=RoomStatus.MAINTENANCE)
        for room in student_rooms.values("room_type", "capacity", "occupied"):
            label = room_type_labels[room["room_type"]]
            vacancy_by_type[label] += max(room["capacity"] - room["occupied"], 0)
        return JsonResponse({
            "generated_at": timezone.localtime().isoformat(),
            "vacancy_by_type": vacancy_by_type,
        })

    return JsonResponse({
        "generated_at": timezone.localtime().isoformat(),
        "rooms": _room_availability_data(rooms),
    })


@role_required(Role.ADMIN)
@require_http_methods(["GET", "POST"])
def room_import(request):
    form = RoomCSVImportForm(request.POST or None, request.FILES or None)
    report = None
    if request.method == "POST" and form.is_valid():
        try:
            report = import_rooms(form.cleaned_data["file"])
        except CSVImportError as exc:
            form.add_error("file", str(exc))
        else:
            if report["accepted"]:
                log_action(
                    "ROOMS_IMPORTED",
                    user=request.user,
                    entity="room_import",
                    new=f"Accepted: {len(report['accepted'])}; rejected: {len(report['rejected'])}",
                    request=request,
                )
    return render(request, "rooms/import.html", {"form": form, "report": report})
