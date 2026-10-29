"""Allocation business logic (SAD 4.4). Views call these; they raise apps.core.exceptions on rule violations."""
import logging
import time
from datetime import date, timedelta

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError, transaction
from django.db.models import Case, Count, IntegerField, Q, Value, When
from django.utils import timezone

from apps.accounts.models import Role
from apps.core.audit import log_action
from apps.core.exceptions import (AccessDenied, AlreadyAllocated, BedUnavailable, BusinessRuleViolation,
                                  DuplicateApplication, GenderMismatch, InvalidTransition, ObjectNotFound,
                                  ProfileIncomplete, RoomUnderMaintenance, RunInProgress, ValidationFailure,
                                  WindowClosed)
from apps.core.sequences import next_number
from apps.notifications.services import APPLICATION_ALLOCATED, APPLICATION_REJECTED, enqueue
from apps.rooms.models import Hostel, Room, RoomStatus, RoomType
from apps.students.models import StudentProfile

from .models import (ACTIVE_STATUSES, Allocation, AllocationStatus, ApplicationStatus, ApplicationWindow,
                     AutoAllocateRun, ChangeStatus, RoomApplication, RoomChangeRequest, RunStatus)
from .signals import allocation_created

logger = logging.getLogger("hms.allocation")

# FR-4.4 priority groups, lowest number first in the queue.
GROUP_YEAR_1, GROUP_PRIORITY, GROUP_STANDARD = 0, 1, 2


def get_open_window(today=None):
    """FR-4.1: the window whose start and end dates include today, or None."""
    today = today or timezone.localdate()
    return ApplicationWindow.objects.filter(start_date__lte=today, end_date__gte=today).first()


def student_allocation_history(student):
    """FR-5.5: allocation records belonging only to one student."""
    if student is None:
        return Allocation.objects.none()
    return (Allocation.objects.filter(student=student)
            .select_related("room__hostel")
            .order_by("-start_date", "-created_at", "-pk"))


def scoped_allocation_history(actor, query=""):
    """FR-5.5: allocation history visible to Wardens in their hostels and Administrators."""
    hostels = scoped_hostels(actor)
    allocations = (
        Allocation.objects.filter(room__hostel__in=hostels)
        .select_related("student", "room__hostel")
        .order_by("-start_date", "-created_at", "-pk")
    )
    query = query.strip()
    if query:
        allocations = allocations.filter(
            Q(student__srn__icontains=query) | Q(student__name__icontains=query)
        )
    return allocations


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
    return _in_queue_order(qs)


def _in_queue_order(qs):
    """FR-4.4 order: Year 1, then priority flag, then everyone else; oldest first within each group."""
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
    started = time.perf_counter()                           # NFR-PERF-2: whole transaction, incl. commit
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
        # FR-4.10: queued in this transaction, so a rollback removes it.
        enqueue(APPLICATION_ALLOCATED, student.user.email, application.application_no, {
            "application_no": application.application_no, "hostel": room.hostel.name, "room": room.room_no,
            "bed": bed_no, "status": AllocationStatus.PROVISIONAL.label})
    # SAD 4.4.4: ids only, no personal data. Alert when p95 of allocation_ms is above 1000.
    elapsed_ms = round((time.perf_counter() - started) * 1000, 1)
    logger.info("allocation created", extra={"allocation_ms": elapsed_ms, "allocation_id": allocation.pk})
    return allocation


def reject(application, reason, actor):
    """FR-4.8: reject a pending application with a reason of at least 10 characters."""
    with transaction.atomic():
        if not scoped_applications(actor).filter(pk=application.pk).exists():   # AccessDenied for non-staff
            raise ObjectNotFound()
        application = RoomApplication.objects.select_for_update().select_related("student__user").get(
            pk=application.pk)
        if application.status != ApplicationStatus.PENDING:
            raise BusinessRuleViolation("This application is no longer pending.")
        reason = (reason or "").strip()
        if len(reason) < 10:
            raise ValidationFailure("Enter a reason of at least 10 characters.")
        if len(reason) > RoomApplication._meta.get_field("rejection_reason").max_length:
            raise ValidationFailure("Keep the reason to 300 characters or fewer.")

        application.status = ApplicationStatus.REJECTED
        application.rejection_reason = reason
        application.save(update_fields=["status", "rejection_reason", "updated_at"])
        log_action("REJECT", user=actor, entity="application", entity_id=application.pk,
                   old="application PENDING", new="application REJECTED")
        enqueue(APPLICATION_REJECTED, application.student.user.email, application.application_no, {
            "application_no": application.application_no, "academic_year": application.academic_year,
            "reason": reason})
    return application


ROOM_CHANGE_WAIT_DAYS = 30


def student_room_change_data(student):
    """FR-5.1, FR-5.3: return a student's confirmed allocation and their requests."""
    if student is None:
        return {"allocation": None, "eligible_on": None, "can_request": False, "requests": []}

    allocation = (Allocation.objects.filter(student=student, status=AllocationStatus.CONFIRMED)
                  .select_related("room__hostel").first())
    eligible_on = allocation.start_date + timedelta(days=ROOM_CHANGE_WAIT_DAYS) if allocation else None
    return {
        "allocation": allocation,
        "eligible_on": eligible_on,
        "can_request": allocation is not None and timezone.localdate() >= eligible_on,
        "requests": (RoomChangeRequest.objects.filter(student=student)
                     .select_related("from_allocation__room__hostel").order_by("-created_at", "-pk")),
    }


def submit_room_change_request(student, reason, request=None):
    """FR-5.1: submit a request for a confirmed allocation after the 30-day wait."""
    reason = (reason or "").strip()
    max_length = RoomChangeRequest._meta.get_field("reason").max_length
    if len(reason) < 10:
        raise ValidationFailure("Enter a reason of at least 10 characters.")
    if len(reason) > max_length:
        raise ValidationFailure(f"Keep the reason to {max_length} characters or fewer.")

    try:
        with transaction.atomic():
            student = StudentProfile.objects.select_for_update().get(pk=student.pk)
            if student.change_requests.filter(status=ChangeStatus.PENDING).exists():
                raise BusinessRuleViolation("You already have a pending room change request.")

            allocation = (Allocation.objects.select_for_update()
                          .filter(student=student, status=AllocationStatus.CONFIRMED)
                          .select_related("room__hostel").first())
            if allocation is None:
                raise BusinessRuleViolation("A confirmed allocation is required to request a room change.")

            eligible_on = allocation.start_date + timedelta(days=ROOM_CHANGE_WAIT_DAYS)
            if timezone.localdate() < eligible_on:
                raise BusinessRuleViolation(
                    f"You can request a room change on or after {eligible_on:%d-%m-%Y}."
                )

            change_request = RoomChangeRequest.objects.create(
                student=student, from_allocation=allocation, reason=reason,
            )
            log_action("ROOM_CHANGE_REQUEST_SUBMITTED", user=student.user, entity="room_change_request",
                       entity_id=change_request.pk, new=f"allocation {allocation.pk}; status PENDING",
                       request=request)
    except IntegrityError as exc:
        if RoomChangeRequest.objects.filter(student_id=student.pk, status=ChangeStatus.PENDING).exists():
            raise BusinessRuleViolation("You already have a pending room change request.") from exc
        raise
    return change_request


def _scoped_room_change_requests(actor):
    if actor.role not in (Role.WARDEN, Role.ADMIN):
        raise AccessDenied()
    return RoomChangeRequest.objects.filter(from_allocation__room__hostel__in=scoped_hostels(actor))


def list_pending_room_change_requests(actor):
    """FR-5.3: pending requests for hostels managed by this Warden or Administrator."""
    return (_scoped_room_change_requests(actor).filter(status=ChangeStatus.PENDING)
            .select_related("student", "from_allocation__room__hostel").order_by("created_at", "pk"))


def get_room_change_request(pk, actor):
    """Return one request only when it belongs to a hostel in the actor's scope."""
    try:
        return (_scoped_room_change_requests(actor)
                .select_related("student", "from_allocation__room__hostel").get(pk=pk))
    except RoomChangeRequest.DoesNotExist:
        raise ObjectNotFound()


def reject_room_change_request(change_request, reason, actor):
    """FR-5.3: reject a pending request and retain the reason for the student."""
    if actor.role not in (Role.WARDEN, Role.ADMIN):
        raise AccessDenied()
    reason = (reason or "").strip()
    max_length = RoomChangeRequest._meta.get_field("decision_reason").max_length
    if not reason:
        raise ValidationFailure("Enter a rejection reason.")
    if len(reason) > max_length:
        raise ValidationFailure(f"Keep the rejection reason to {max_length} characters or fewer.")

    with transaction.atomic():
        try:
            change_request = (_scoped_room_change_requests(actor).select_for_update()
                              .get(pk=change_request.pk))
        except RoomChangeRequest.DoesNotExist:
            raise ObjectNotFound()
        if change_request.status != ChangeStatus.PENDING:
            raise BusinessRuleViolation("This room change request is no longer pending.")

        change_request.status = ChangeStatus.REJECTED
        change_request.decision_reason = reason
        change_request.decided_by = actor
        change_request.save(update_fields=["status", "decision_reason", "decided_by", "updated_at"])
        log_action("ROOM_CHANGE_REQUEST_REJECTED", user=actor, entity="room_change_request",
                   entity_id=change_request.pk, old=ChangeStatus.PENDING.label,
                   new=f"{ChangeStatus.REJECTED.label}; {reason}")
    return change_request


def room_change_bed_options(change_request, actor):
    """Available destination beds in hostels this Warden or Administrator can manage."""
    if not _scoped_room_change_requests(actor).filter(pk=change_request.pk).exists():
        raise ObjectNotFound()

    rooms = (Room.objects.filter(hostel__in=scoped_hostels(actor), hostel__is_active=True,
                                 hostel__gender_type=change_request.student.gender, is_active=True)
             .exclude(status=RoomStatus.MAINTENANCE).select_related("hostel"))
    held = set(Allocation.objects.active().filter(room__in=rooms).values_list("room_id", "bed_no"))
    return [
        (f"{room.pk}:{bed_no}",
         f"{room.hostel.name} - Room {room.room_no} ({room.get_room_type_display()}) - Bed {bed_no}")
        for room in rooms.order_by("pk")
        for bed_no in range(1, room.capacity + 1)
        if (room.pk, bed_no) not in held
    ]


def approve_room_change_request(change_request, room, bed_no, actor, request=None):
    """FR-5.2: move a student atomically to a vacant bed and retain their fee history."""
    if actor.role not in (Role.WARDEN, Role.ADMIN):
        raise AccessDenied()

    initial = get_room_change_request(change_request.pk, actor)
    old_allocation_id = initial.from_allocation_id
    old_room_id = initial.from_allocation.room_id
    today = timezone.localdate()

    with transaction.atomic():
        room_ids = sorted({old_room_id, room.pk})
        locked_rooms = list(Room.objects.select_for_update().filter(pk__in=room_ids).order_by("pk"))
        room_by_id = {locked.pk: locked for locked in locked_rooms}
        if len(room_by_id) != len(room_ids):
            raise ObjectNotFound()
        old_room = room_by_id[old_room_id]
        destination = room_by_id[room.pk]

        try:
            change_request = RoomChangeRequest.objects.select_for_update().get(pk=initial.pk)
        except RoomChangeRequest.DoesNotExist:
            raise ObjectNotFound()
        if change_request.status != ChangeStatus.PENDING:
            raise BusinessRuleViolation("This room change request is no longer pending.")
        if change_request.from_allocation_id != old_allocation_id:
            raise BusinessRuleViolation("The allocation for this request has changed.")
        if not _scoped_room_change_requests(actor).filter(pk=change_request.pk).exists():
            raise ObjectNotFound()
        if not scoped_hostels(actor).filter(pk=destination.hostel_id, is_active=True).exists():
            raise ObjectNotFound()

        try:
            old_allocation = Allocation.objects.select_for_update().get(
                pk=old_allocation_id, student_id=change_request.student_id)
        except Allocation.DoesNotExist:
            raise BusinessRuleViolation("The student's original allocation is no longer active.")
        if old_allocation.status not in ACTIVE_STATUSES:
            raise BusinessRuleViolation("The student's original allocation is no longer active.")
        if Allocation.objects.active().filter(student_id=change_request.student_id).exclude(
                pk=old_allocation.pk).exists():
            raise AlreadyAllocated()

        destination_hostel = Hostel.objects.get(pk=destination.hostel_id)
        if destination_hostel.gender_type != change_request.student.gender:
            raise GenderMismatch()
        if destination.status == RoomStatus.MAINTENANCE:
            raise RoomUnderMaintenance()
        if not destination.is_active or not destination_hostel.is_active:
            raise BedUnavailable()
        if not isinstance(bed_no, int) or not 1 <= bed_no <= destination.capacity:
            raise ValidationFailure(f"Choose a bed between 1 and {destination.capacity}.")
        if _bed_is_held(destination, bed_no):
            raise BedUnavailable()

        from apps.fees.services import create_fee_record, move_fee_record

        create_fee_record(old_allocation)
        old_allocation.status = AllocationStatus.ENDED
        old_allocation.end_date = today
        old_allocation.end_reason = "Room change approved"
        old_allocation.save(update_fields=["status", "end_date", "end_reason", "updated_at"])

        try:
            with transaction.atomic():
                replacement = Allocation.objects.create(
                    student=change_request.student, room=destination, bed_no=bed_no,
                    academic_year=old_allocation.academic_year, start_date=today,
                    end_date=_next_31_may(today), status=AllocationStatus.PROVISIONAL,
                )
        except (IntegrityError, DjangoValidationError) as exc:
            if Allocation.objects.active().filter(room=destination, bed_no=bed_no).exists():
                raise BedUnavailable()
            if Allocation.objects.active().filter(student_id=change_request.student_id).exists():
                raise AlreadyAllocated()
            if isinstance(exc, DjangoValidationError) and any(
                    "There are no vacant beds" in message for message in exc.messages):
                raise BedUnavailable() from exc
            raise

        fee_record = move_fee_record(old_allocation, replacement, destination.annual_fee)
        replacement.status = (AllocationStatus.CONFIRMED if fee_record.amount_paid >= fee_record.total_amount
                              else AllocationStatus.PROVISIONAL)
        replacement.save(update_fields=["status", "updated_at"])

        old_room.refresh_status()
        if destination.pk != old_room.pk:
            destination.refresh_status()

        change_request.status = ChangeStatus.APPROVED
        change_request.decided_by = actor
        change_request.save(update_fields=["status", "decided_by", "updated_at"])
        log_action(
            "ROOM_CHANGE_REQUEST_APPROVED", user=actor, entity="room_change_request",
            entity_id=change_request.pk, old=f"allocation {old_allocation.pk} active",
            new=(f"allocation {old_allocation.pk} ended; allocation {replacement.pk} "
                 f"created at {destination} bed {bed_no}; fee total {fee_record.total_amount}"),
            request=request,
        )
    return replacement


def list_active_allocations_for_warden(actor):
    """FR-5.4: active allocations in the Warden's assigned active hostels."""
    if actor.role != Role.WARDEN:
        raise AccessDenied()
    return (Allocation.objects.active().filter(room__hostel__in=scoped_hostels(actor))
            .select_related("student", "room__hostel").order_by("room__hostel__name", "room__room_no", "bed_no"))


def get_active_allocation_for_warden(pk, actor):
    """Return one active allocation only when its hostel is in the Warden's scope."""
    if actor.role != Role.WARDEN:
        raise AccessDenied()
    try:
        return (Allocation.objects.active().filter(room__hostel__in=scoped_hostels(actor))
                .select_related("student", "room__hostel").get(pk=pk))
    except Allocation.DoesNotExist:
        raise ObjectNotFound()


def check_out_allocation(allocation, checkout_date, actor, request=None):
    """FR-5.4: end an active allocation and release its bed atomically."""
    if actor.role != Role.WARDEN:
        raise AccessDenied()
    if not scoped_hostels(actor).filter(pk=allocation.room.hostel_id).exists():
        raise ObjectNotFound()

    with transaction.atomic():
        room = Room.objects.select_for_update().get(pk=allocation.room_id)
        try:
            allocation = Allocation.objects.select_for_update().get(pk=allocation.pk)
        except Allocation.DoesNotExist:
            raise ObjectNotFound()
        if allocation.status not in ACTIVE_STATUSES:
            raise BusinessRuleViolation("This allocation is no longer active.")
        today = timezone.localdate()
        if checkout_date > today:
            raise ValidationFailure("Check-out date cannot be in the future.")
        if checkout_date < allocation.start_date:
            raise ValidationFailure("Check-out date cannot be before the allocation start date.")

        old_status = allocation.status
        allocation.status = AllocationStatus.ENDED
        allocation.end_date = checkout_date
        allocation.end_reason = "Student checked out"
        allocation.save(update_fields=["status", "end_date", "end_reason", "updated_at"])
        room.refresh_status()
        log_action(
            "CHECK_OUT", user=actor, entity="allocation", entity_id=allocation.pk,
            old=old_status, new=f"{AllocationStatus.ENDED.label} on {checkout_date:%Y-%m-%d}",
            request=request,
        )
    return allocation


def confirm(allocation):
    """FR-4.9: Provisional -> Confirmed.

    Called only by the fees service when the allocation's fee record becomes Paid (FR-7.3, issue #29).
    """
    with transaction.atomic():
        allocation = Allocation.objects.select_for_update().get(pk=allocation.pk)
        if allocation.status != AllocationStatus.PROVISIONAL:
            raise InvalidTransition()
        allocation.status = AllocationStatus.CONFIRMED
        allocation.save(update_fields=["status", "updated_at"])
        log_action("CONFIRM", entity="allocation", entity_id=allocation.pk,
                   old=AllocationStatus.PROVISIONAL.label, new=AllocationStatus.CONFIRMED.label)
    return allocation


NO_PREFERRED_BED = "No vacant bed of the preferred room types."


def _vacant_bed_map(hostel):
    """Return vacant beds and active roommate rooms for one hostel."""
    rooms = list(
        Room.objects.filter(hostel=hostel, is_active=True).exclude(status=RoomStatus.MAINTENANCE)
        .select_related("hostel").order_by("floor", "room_no")
    )
    eligible_room_ids = {room.pk for room in rooms}
    held = {}
    roommate_rooms = {}
    allocations = (Allocation.objects.active().filter(room__hostel=hostel)
                   .values_list("room_id", "bed_no", "student__srn", "room__room_type"))
    for room_id, bed_no, srn, room_type in allocations:
        roommate_rooms[(srn, room_type)] = room_id
        if room_id in eligible_room_ids:
            held.setdefault(room_id, set()).add(bed_no)

    beds = {t: [] for t in RoomType.values}
    for room in rooms:
        beds[room.room_type].extend(
            (room, n) for n in range(1, room.capacity + 1) if n not in held.get(room.pk, set())
        )
    return beds, roommate_rooms


def _auto_allocate_one(application, beds, roommate_rooms, actor):
    """Try each preference in order. Returns (allocation, None) or (None, reason)."""
    preferences = [p for p in (application.preference_1, application.preference_2, application.preference_3) if p]
    for pref in preferences:
        roommate_room = roommate_rooms.get((application.preferred_roommate_srn, pref))
        # Best effort (SAD 4.1.5): the roommate's room first, then the rest in floor/room/bed order.
        ordered = sorted(beds[pref], key=lambda bed: bed[0].pk != roommate_room)
        for room, bed_no in ordered:
            try:
                allocation = allocate(application, room, bed_no, actor)
            except BedUnavailable:
                beds[pref].remove((room, bed_no))      # taken by someone else meanwhile: try the next bed
                continue
            except BusinessRuleViolation as exc:       # GenderMismatch, RoomUnderMaintenance, AlreadyAllocated, ...
                return None, exc.message
            beds[pref].remove((room, bed_no))
            return allocation, None
    return None, NO_PREFERRED_BED


def auto_allocate(hostel, actor):
    """FR-4.7: allocate the pending applications for one hostel in FR-4.4 order (SAD 4.1.5).

    Deliberately not one big transaction: each bed goes through allocate() in its own short
    transaction, so a conflict affects only that application.
    """
    if actor.role not in (Role.WARDEN, Role.ADMIN):
        raise AccessDenied()
    if actor.role == Role.WARDEN and not actor.hostels.filter(pk=hostel.pk).exists():
        raise ObjectNotFound()
    if not hostel.is_active:
        raise BusinessRuleViolation("This hostel is inactive.")

    try:
        with transaction.atomic():
            run = AutoAllocateRun.objects.create(hostel=hostel, started_by=actor, status=RunStatus.RUNNING)
    except IntegrityError:
        # uniq_running_autoalloc_per_hostel
        raise RunInProgress("Auto-Allocate is already running for this hostel.")

    allocated, unallocated = [], []
    try:
        # NFR-SAFE-2: only students whose gender matches the hostel are considered.
        pending = _in_queue_order(RoomApplication.objects.filter(status=ApplicationStatus.PENDING,
                                                                 student__gender=hostel.gender_type))
        beds, roommate_rooms = _vacant_bed_map(hostel)
        for application in list(pending):
            allocation, reason = _auto_allocate_one(application, beds, roommate_rooms, actor)
            if allocation:
                roommate_rooms[(application.student.srn, allocation.room.room_type)] = allocation.room_id
                allocated.append({"application_no": application.application_no, "srn": application.student.srn,
                                  "room": allocation.room, "bed": allocation.bed_no})
            else:
                unallocated.append({"application_no": application.application_no, "srn": application.student.srn,
                                    "reason": reason})
    except Exception:
        run.status = RunStatus.FAILED
        run.finished_at = timezone.now()
        run.allocated_count, run.unallocated_count = len(allocated), len(unallocated)
        run.save(update_fields=["status", "finished_at", "allocated_count", "unallocated_count"])
        raise

    run.status = RunStatus.DONE
    run.finished_at = timezone.now()
    run.allocated_count, run.unallocated_count = len(allocated), len(unallocated)
    run.save(update_fields=["status", "finished_at", "allocated_count", "unallocated_count"])
    log_action("AUTO_ALLOCATE", user=actor, entity="auto_allocate_run", entity_id=run.pk, old="",
               new=f"{len(allocated)} allocated, {len(unallocated)} unallocated")
    return {"run": run, "allocated": allocated, "unallocated": unallocated}
