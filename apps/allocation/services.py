"""Allocation business logic (SAD 4.4). Views call these; they raise apps.core.exceptions on rule violations."""
from django.db import IntegrityError, transaction
from django.db.models import Case, Count, IntegerField, Q, Value, When
from django.utils import timezone

from apps.accounts.models import Role
from apps.core.audit import log_action
from apps.core.exceptions import (AccessDenied, DuplicateApplication, ProfileIncomplete, ValidationFailure,
                                  WindowClosed)
from apps.core.sequences import next_number
from apps.rooms.models import Room, RoomStatus, RoomType

from .models import ACTIVE_STATUSES, ApplicationStatus, ApplicationWindow, RoomApplication

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


def list_pending(actor, year=None, preference=None):
    """FR-4.4: pending applications by priority group, then oldest first.

    SAD DD-1: a Warden sees a student only if the student's gender matches one of the Warden's hostels.
    """
    if actor.role == Role.ADMIN:
        qs = RoomApplication.objects.all()
    elif actor.role == Role.WARDEN:
        genders = actor.hostels.filter(is_active=True).values("gender_type")
        qs = RoomApplication.objects.filter(student__gender__in=genders)
    else:
        raise AccessDenied()

    qs = qs.filter(status=ApplicationStatus.PENDING)
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
