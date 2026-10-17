"""Allocation business logic (SAD 4.4). Views call these; they raise apps.core.exceptions on rule violations."""
from django.utils import timezone

from apps.core.exceptions import WindowClosed

from .models import ApplicationWindow


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
