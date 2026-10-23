
"""Allocation business logic (SAD 4.4). Views call these; they raise apps.core.exceptions on rule violations."""

from datetime import date

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import Case, Count, IntegerField, Q, Value, When
from django.utils import timezone

from apps.accounts.models import Role
from apps.core.audit import log_action
from apps.core.exceptions import (
    AccessDenied,
    AlreadyAllocated,
    BedUnavailable,
    BusinessRuleViolation,
    DuplicateApplication,
    GenderMismatch,
    ObjectNotFound,
    ProfileIncomplete,
    RoomUnderMaintenance,
    ValidationFailure,
    WindowClosed,
)
from apps.core.sequences import next_number
from apps.rooms.models import Hostel, Room, RoomStatus, RoomType

from .models import (
    ACTIVE_STATUSES,
    Allocation,
    AllocationStatus,
    ApplicationStatus,
    ApplicationWindow,
    RoomApplication,
)
from .signals import allocation_created
