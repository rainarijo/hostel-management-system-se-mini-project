"""Allocation business logic (SAD 4.4). Views call these; they raise apps.core.exceptions on rule violations."""
from django.db import IntegrityError, transaction
from django.db.models import Count, Q
from django.utils import timezone

from apps.core.audit import log_action
from apps.core.exceptions import DuplicateApplication, ProfileIncomplete, ValidationFailure, WindowClosed
from apps.core.sequences import next_number
from apps.rooms.models import Room, RoomStatus, RoomType

from .models import ACTIVE_STATUSES, ApplicationWindow, RoomApplication


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
