"""Allocation business logic (SAD 4.4). Views call these; they raise apps.core.exceptions on rule violations."""
from datetime import date

from django.db import IntegrityError, transaction
from django.db.models import Case, Count, IntegerField, Q, Value, When
from django.utils import timezone

from apps.accounts.models import Role
from apps.core.audit import log_action
from apps.core.exceptions import (AccessDenied, AlreadyAllocated, BedUnavailable, BusinessRuleViolation,
                                  DuplicateApplication, GenderMismatch, ObjectNotFound, ProfileIncomplete,
                                  RoomUnderMaintenance, ValidationFailure, WindowClosed)
from apps.core.sequences import next_number
from apps.rooms.models import Hostel, Room, RoomStatus, RoomType

from .models import (ACTIVE_STATUSES, Allocation, AllocationStatus, ApplicationStatus, ApplicationWindow,
                     RoomApplication)
from .signals import allocation_created

# FR-4.4 priority groups, lowest number first in the queue.
GROUP_YEAR_1, GROUP_PRIORITY, GROUP_STANDARD = 0, 1, 2


def get_open_window(today=None):
    """FR-4.1: the window whose start and end dates include today, or None."""
    today = today or timezone.localdate()
    return ApplicationWindow.objects.filter(start_date__lte=today, end_date__gte=today).first()


def require_open_window(today=None):
    """FR-4.1: the open window, or raise WindowClosed."""
    window = get_open_window(today)
    if window is None:
        raise WindowClosed()
    return window


def window_status(window, today=None):
    today = today or timezone.localdate()
    if today < window.start_date:
        return "Upcoming"
    if today > window.end_date:
        return "Closed"
    return "Open"


def submit_application(student, preferences, roommate_srn="", request=None):
    """FR-4.2, FR-4.3: one application per student per academic year, only inside the open window."""
    preferences = list(preferences)
    distinct = len(set(preferences)) == len(preferences)
    if not 1 <= len(preferences) <= 3 or not distinct or any(p not in RoomType.values for p in preferences):
        raise ValidationFailure("Choose 1 to 3 different room types.")
    try:
        with transaction.atomic():
            window = require_open_window()
            if not student.is_complete:
                raise ProfileIncomplete()
            if student.applications.filter(academic_year=window.academic_year).exists():
                raise DuplicateApplication()
            padded = preferences + [""] * (3 - len(preferences))
            application = RoomApplication.objects.create(
                student=student, academic_year=window.academic_year,
                preference_1=padded[0], preference_2=padded[1], preference_3=padded[2],
                preferred_roommate_srn=roommate_srn, application_no=next_number("APP"))
            log_action("APPLICATION_SUBMITTED", user=student.user, entity="room_application",
                       entity_id=application.application_no,
                       new=f"{window.academic_year}: {', '.join(preferences)}; roommate {roommate_srn or '-'}",
                       request=request)
            # TODO(#30): enqueue APPLICATION_RECEIVED notification
    except IntegrityError:
        # uniq_application_per_year: a concurrent request saved an application first.
        raise DuplicateApplication()
    return application


def vacancy_by_room_type(student):
    """FR-4.2: vacant beds per room type in hostels for the student's gender. Counts only, never room numbers."""
    rooms = (Room.objects.filter(hostel__gender_type=student.gender, hostel__is_active=True, is_active=True)
             .exclude(status=RoomStatus.MAINTENANCE)
             .annotate(occupied=Count("allocations", filter=Q(allocations__status__in=ACTIVE_STATUSES))))
    vacancy = {t: 0 for t in RoomType.values}
    for room in rooms:
        vacancy[room.room_type] += max(room.capacity - room.occupied, 0)
    return vacancy


def scoped_hostels(actor):
    """Hostels the actor manages: all for the Administrator, assigned active hostels for a Warden."""
    if actor.role == Role.ADMIN:
        return Hostel.objects.all()
    if actor.role == Role.WARDEN:
        return actor.hostels.filter(is_active=True)
    raise AccessDenied()


def scoped_applications(actor):
    """SAD DD-1: a Warden sees a student only if the student's gender matches one of the Warden's hostels."""
    if actor.role == Role.ADMIN:
        return RoomApplication.objects.all()
    return RoomApplication.objects.filter(student__gender__in=scoped_hostels(actor).values("gender_type"))


def list_pending(actor, year=None, preference=None):
    """FR-4.4: pending applications by priority group, then oldest first.

    SAD DD-1: a Warden sees a student only if the student's gender matches one of the Warden's hostels.
    """
    qs = scoped_applications(actor).filter(status=ApplicationStatus.PENDING)
    if year:
        qs = qs.filter(student__year=year)
    if preference:
        qs = qs.filter(Q(preference_1=preference) | Q(preference_2=preference) | Q(preference_3=preference))
    return (qs.select_related("student")
            .annotate(priority_group=Case(
                When(student__year=1, then=Value(GROUP_YEAR_1)),
                When(student__priority_flag=True, then=Value(GROUP_PRIORITY)),
                default=Value(GROUP_STANDARD), output_field=IntegerField()))
            .order_by("priority_group", "submitted_at", "pk"))


def _bed_is_held(room, bed_no):
    return Allocation.objects.active().filter(room=room, bed_no=bed_no).exists()


def _next_31_may(today):
    end = date(today.year, 5, 31)
    return end if today <= end else date(today.year + 1, 5, 31)


def candidate_beds(application, actor):
    """FR-4.5: vacant beds the actor may offer this student, preferred room types first."""
    student = application.student
    rooms = (Room.objects.filter(hostel__in=scoped_hostels(actor), hostel__is_active=True, is_active=True,
                                 hostel__gender_type=student.gender)
             .exclude(status=RoomStatus.MAINTENANCE).select_related("hostel"))
    held = {}
    for room_id, bed_no in Allocation.objects.active().filter(room__in=rooms).values_list("room_id", "bed_no"):
        held.setdefault(room_id, set()).add(bed_no)

    preferences = [p for p in (application.preference_1, application.preference_2, application.preference_3) if p]

    def rank(room):
        pref = preferences.index(room.room_type) if room.room_type in preferences else len(preferences)
        return (pref, room.hostel.name, room.floor, room.room_no)

    return [(room, bed_no) for room in sorted(rooms, key=rank)
            for bed_no in range(1, room.capacity + 1) if bed_no not in held.get(room.pk, set())]


def allocate(application, room, bed_no, actor):
    """FR-4.5, FR-4.6: give one vacant bed to a pending application. All or nothing.

    The pre-checks give friendly messages; the database constraints uniq_active_bed and
    uniq_active_allocation_per_student are the real guarantee under concurrent requests.
    """
    with transaction.atomic():
        hostels = scoped_hostels(actor)                     # AccessDenied for anyone but Warden/Admin
        in_scope = (scoped_applications(actor).filter(pk=application.pk).exists()
                    and hostels.filter(pk=room.hostel_id).exists())
        if not in_scope:
            raise ObjectNotFound()

        room = Room.objects.select_for_update().select_related("hostel").get(pk=room.pk)
        application = RoomApplication.objects.select_for_update().select_related("student").get(pk=application.pk)
        if application.status != ApplicationStatus.PENDING:
            raise BusinessRuleViolation("This application is no longer pending.")
        student = application.student

        if Allocation.objects.active().filter(student=student).exists():
            raise AlreadyAllocated()
        if room.hostel.gender_type != student.gender:
            raise GenderMismatch()
        if room.status == RoomStatus.MAINTENANCE:
            raise RoomUnderMaintenance()
        if not room.is_active or not room.hostel.is_active:
            raise BedUnavailable()
        if not 1 <= bed_no <= room.capacity:
            raise ValidationFailure(f"Choose a bed between 1 and {room.capacity}.")
        if _bed_is_held(room, bed_no):
            raise BedUnavailable()

        today = timezone.localdate()
        try:
            with transaction.atomic():
                allocation = Allocation.objects.create(
                    student=student, room=room, bed_no=bed_no, application=application,
                    academic_year=application.academic_year, start_date=today, end_date=_next_31_may(today),
                    status=AllocationStatus.PROVISIONAL)
        except IntegrityError:
            # Another request won the race. Check the database, not the error text (SQLite and PostgreSQL differ).
            if Allocation.objects.active().filter(room=room, bed_no=bed_no).exists():
                raise BedUnavailable()
            if Allocation.objects.active().filter(student=student).exists():
                raise AlreadyAllocated()
            raise

        application.status = ApplicationStatus.ALLOCATED
        application.save(update_fields=["status", "updated_at"])
        room.refresh_status()
        allocation_created.send(sender=Allocation, allocation=allocation)
        log_action("ALLOCATE", user=actor, entity="allocation", entity_id=allocation.pk, old="application PENDING",
                   new=f"{room} bed {bed_no} {AllocationStatus.PROVISIONAL.label}")
        # TODO(#6/#30): enqueue APPLICATION_ALLOCATED notification
    return allocation
