from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from apps.accounts.models import Role
from apps.core.audit import log_action
from apps.core.permissions import role_required

from .forms import ApplicationWindowForm
from .models import ApplicationWindow
from .services import window_status


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
