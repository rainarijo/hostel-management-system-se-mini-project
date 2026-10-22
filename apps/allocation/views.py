from django.contrib import messages
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from apps.accounts.models import Role
from apps.core.audit import log_action
from apps.core.exceptions import BusinessRuleViolation, ProfileIncomplete
from apps.core.permissions import role_required
from apps.rooms.models import RoomType

from .forms import ApplicationForm, ApplicationWindowForm
from .models import ApplicationWindow, RoomApplication
from .services import (GROUP_PRIORITY, GROUP_YEAR_1, get_open_window, list_pending, submit_application,
                       vacancy_by_room_type, window_status)

YEAR_CHOICES = (1, 2, 3, 4)
GROUP_BADGES = {GROUP_YEAR_1: ("Year 1", "text-bg-success"), GROUP_PRIORITY: ("Priority", "text-bg-warning")}


@role_required(Role.STUDENT, Role.WARDEN, Role.ADMIN)
def index(request):
    """Room applications and allocation (FR-4.1 - FR-4.10, FR-5.1 - FR-5.5).

    Planned for Sprint 2: replace this placeholder.
    """
    context = {"feature": "Room applications and allocation", "frs": "FR-4.1 - FR-4.10, FR-5.1 - FR-5.5", "sprint": 2}
    return render(request, "coming_soon.html", context)


@role_required(Role.ADMIN)
def window_list(request):
    """FR-4.1: all application windows, newest first."""
    today = timezone.localdate()
    windows = ApplicationWindow.objects.order_by("-academic_year")
    rows = [(w, window_status(w, today)) for w in windows]
    return render(request, "allocation/window_list.html", {"rows": rows})


@role_required(Role.ADMIN)
def window_create(request):
    form = ApplicationWindowForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        window = form.save(commit=False)
        window.created_by = request.user
        window.save()
        log_action("WINDOW_CREATED", user=request.user, entity="application_window", entity_id=window.pk,
                   new=str(window), request=request)
        messages.success(request, f"Application window for {window.academic_year} created.")
        return redirect("allocation:window_list")
    return render(request, "allocation/window_form.html", {"form": form, "is_new": True})


@role_required(Role.ADMIN)
def window_edit(request, pk):
    window = get_object_or_404(ApplicationWindow, pk=pk)
    old = str(window)
    form = ApplicationWindowForm(request.POST or None, instance=window)
    if request.method == "POST" and form.is_valid():
        window = form.save()
        log_action("WINDOW_UPDATED", user=request.user, entity="application_window", entity_id=window.pk,
                   old=old, new=str(window), request=request)
        messages.success(request, f"Application window for {window.academic_year} updated.")
        return redirect("allocation:window_list")
    return render(request, "allocation/window_form.html", {"form": form, "is_new": False, "window": window})


@role_required(Role.STUDENT)
def apply(request):
    """FR-4.2, FR-4.3: submit one room application for the open window."""
    student = getattr(request.user, "student_profile", None)
    vacancy = vacancy_by_room_type(student) if student else {}
    form = ApplicationForm(request.POST or None, student=student, vacancy=vacancy)
    error, status = None, 200
    if request.method == "POST" and form.is_valid():
        try:
            if student is None:
                raise ProfileIncomplete()
            application = submit_application(student, form.preferences,
                                             form.cleaned_data["preferred_roommate_srn"], request=request)
        except BusinessRuleViolation as exc:
            error, status = exc.message, 409
        else:
            messages.success(request, f"Application {application.application_no} submitted.")
            return redirect("allocation:application_detail", application_no=application.application_no)

    window = get_open_window()
    existing = None
    if window and student:
        existing = student.applications.filter(academic_year=window.academic_year).first()
    return render(request, "allocation/apply.html", {
        "form": form, "window": window, "existing": existing, "error": error, "student": student,
        "vacancy": [(label, vacancy.get(value, 0)) for value, label in RoomType.choices],
    }, status=status)


@role_required(Role.STUDENT)
def application_detail(request, application_no):
    """FR-4.3: a student can open only their own application."""
    application = get_object_or_404(RoomApplication, application_no=application_no, student__user=request.user)
    preferences = [getattr(application, f"get_preference_{n}_display")() for n in (1, 2, 3)
                   if getattr(application, f"preference_{n}")]
    return render(request, "allocation/application_detail.html",
                  {"application": application, "preferences": preferences})


@role_required(Role.WARDEN, Role.ADMIN)
def queue(request):
    """FR-4.4: pending applications in priority order, filterable by year and room-type preference."""
    year = request.GET.get("year", "")
    year = int(year) if year.isdigit() and int(year) in YEAR_CHOICES else None
    pref = request.GET.get("pref", "")
    pref = pref if pref in RoomType.values else None

    page = Paginator(list_pending(request.user, year=year, preference=pref), 25).get_page(request.GET.get("page"))
    for application in page:
        application.badge = GROUP_BADGES.get(application.priority_group, ("Standard", "text-bg-secondary"))
        application.preferences = [getattr(application, f"get_preference_{n}_display")() for n in (1, 2, 3)
                                   if getattr(application, f"preference_{n}")]
    filters = request.GET.copy()
    filters.pop("page", None)
    return render(request, "allocation/queue.html", {
        "page": page, "year": year, "pref": pref, "filters": filters.urlencode(),
        "year_choices": YEAR_CHOICES, "room_types": RoomType.choices,
    })
