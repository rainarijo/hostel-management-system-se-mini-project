from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from apps.accounts.models import Role
from apps.core.audit import log_action
from apps.core.exceptions import (AccessDenied, BusinessRuleViolation, ObjectNotFound, ProfileIncomplete,
                                  ValidationFailure)
from apps.core.permissions import role_required
from apps.rooms.models import Room, RoomType

from .forms import ApplicationForm, ApplicationWindowForm
from .models import ApplicationStatus, ApplicationWindow, RoomApplication
from .services import (GROUP_PRIORITY, GROUP_YEAR_1, allocate, candidate_beds, get_open_window, list_pending,
                       scoped_applications, submit_application, vacancy_by_room_type, window_status)

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


def _preferences(application):
    return [getattr(application, f"preference_{n}") for n in (1, 2, 3) if getattr(application, f"preference_{n}")]


def _bed_options(application, actor):
    preferences = _preferences(application)
    options = []
    for room, bed_no in candidate_beds(application, actor):
        label = f"{room.hostel.name} - Room {room.room_no} ({room.get_room_type_display()}) - Bed {bed_no}"
        if room.room_type in preferences:
            label += f" - preference {preferences.index(room.room_type) + 1}"
        options.append((f"{room.pk}:{bed_no}", label))
    return options


@role_required(Role.WARDEN, Role.ADMIN)
def allocate_view(request, pk):
    """FR-4.5, FR-4.6: choose a vacant bed for one pending application."""
    application = get_object_or_404(scoped_applications(request.user).select_related("student"), pk=pk)
    error, field_error, status, chosen = None, None, 200, request.POST.get("bed", "")
    if application.status != ApplicationStatus.PENDING:
        error = "This application is no longer pending."
    elif request.method == "POST":
        room_pk, _, bed_no = chosen.partition(":")
        room = Room.objects.filter(pk=room_pk).first() if room_pk.isdigit() else None
        if room is None or not bed_no.isdigit():
            field_error = "Choose a bed."
        else:
            try:
                allocation = allocate(application, room, int(bed_no), request.user)
            except (ObjectNotFound, Room.DoesNotExist):
                raise Http404
            except AccessDenied:
                raise PermissionDenied
            except BusinessRuleViolation as exc:
                error, status = exc.message, 409
            except ValidationFailure as exc:
                field_error = exc.message
            else:
                messages.success(request, f"{application.application_no} allocated to {allocation.room}, "
                                          f"bed {allocation.bed_no} (Provisional).")
                return redirect("allocation:queue")
        application.refresh_from_db()

    student = application.student
    return render(request, "allocation/allocate.html", {
        "application": application, "student": student, "error": error, "field_error": field_error,
        "chosen": chosen, "pending": application.status == ApplicationStatus.PENDING,
        "preferences": [RoomType(p).label for p in _preferences(application)],
        "options": _bed_options(application, request.user) if application.status == ApplicationStatus.PENDING else [],
    }, status=status)
