from django.contrib import messages
from django.shortcuts import redirect, render

from apps.accounts.models import Role
from apps.allocation.models import Allocation
from apps.core.permissions import role_required

from .forms import AnnouncementForm
from .models import Announcement


@role_required(Role.STUDENT, Role.WARDEN)
def index(request):
    """FR-9.3: list announcements in the user's permitted hostel scope."""
    if request.user.role == Role.STUDENT:
        profile = getattr(request.user, "student_profile", None)
        allocation = None
        announcements = Announcement.objects.none()
        if profile:
            allocation = (
                Allocation.objects.active()
                .filter(student=profile)
                .select_related("room__hostel")
                .first()
            )
            if allocation:
                announcements = Announcement.objects.current().filter(
                    hostel=allocation.room.hostel
                )
        return render(
            request,
            "notifications/index.html",
            {"announcements": announcements, "allocation": allocation, "is_warden": False},
        )

    hostels = request.user.hostels.filter(is_active=True).order_by("name")
    announcements = Announcement.objects.current().filter(hostel__in=hostels)
    return render(
        request,
        "notifications/index.html",
        {"announcements": announcements, "hostels": hostels, "is_warden": True},
    )


@role_required(Role.WARDEN)
def post_announcement(request):
    """FR-9.3: create an announcement within the Warden's hostel scope."""
    if request.method == "POST":
        form = AnnouncementForm(request.POST, warden=request.user)
        if form.is_valid():
            announcement = form.save(commit=False)
            announcement.created_by = request.user
            announcement.save()
            messages.success(request, f'Announcement "{announcement.title}" posted.')
            return redirect("notifications:index")
    else:
        form = AnnouncementForm(warden=request.user)

    return render(request, "notifications/post.html", {"form": form})
