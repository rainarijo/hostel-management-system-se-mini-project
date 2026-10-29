from django.contrib.auth.decorators import login_required
from django.db.models import Sum, Value
from django.db.models.functions import Coalesce
from django.shortcuts import redirect, render
from django.utils import timezone

from apps.accounts.models import Role
from apps.allocation.models import Allocation, ApplicationStatus, RoomApplication
from apps.allocation.services import list_pending
from apps.complaints.models import Complaint
from apps.core.permissions import role_required
from apps.notifications.models import Announcement
from apps.rooms.models import Hostel, Room


@login_required
def home(request):
    """Send each role to its own dashboard (UI-2)."""
    target = {
        Role.STUDENT: "core:student_dashboard",
        Role.WARDEN: "core:warden_dashboard",
        Role.ADMIN: "core:admin_dashboard",
    }[request.user.role]
    return redirect(target)


def _bed_summary(rooms):
    total = rooms.aggregate(total=Coalesce(Sum("capacity"), Value(0)))["total"]
    occupied = Allocation.objects.active().filter(room__in=rooms).count()
    return {"total": total, "occupied": occupied, "vacant": total - occupied,
            "percent": round(occupied * 100 / total) if total else 0}


@role_required(Role.STUDENT)
def student_dashboard(request):
    profile = getattr(request.user, "student_profile", None)
    allocation = application = announcements = None
    if profile:
        allocation = Allocation.objects.active().filter(student=profile).select_related("room__hostel").first()
        application = profile.applications.order_by("-submitted_at").first()
        if allocation:
            announcements = Announcement.objects.current().filter(hostel=allocation.room.hostel)
    return render(request, "core/student_dashboard.html", {
        "profile": profile, "allocation": allocation, "application": application,
        "announcements": announcements or [],
        "open_complaints": profile.complaints.exclude(status__in=["RESOLVED", "REJECTED"]).count() if profile else 0,
    })


@role_required(Role.WARDEN)
def warden_dashboard(request):
    hostels = Hostel.objects.filter(wardens=request.user, is_active=True)
    rooms = Room.objects.filter(hostel__in=hostels, is_active=True)
    overdue = timezone.now() - timezone.timedelta(hours=72)
    return render(request, "core/warden_dashboard.html", {
        "hostels": hostels, "beds": _bed_summary(rooms),
        "pending_applications": list_pending(request.user).count(),
        "overdue_complaints": Complaint.objects.filter(
            room__hostel__in=hostels, status__in=["OPEN", "IN_PROGRESS"], created_at__lt=overdue).count(),
    })


@role_required(Role.ADMIN)
def admin_dashboard(request):
    hostels = Hostel.objects.filter(is_active=True)
    rooms = Room.objects.filter(hostel__in=hostels, is_active=True)
    overdue = timezone.now() - timezone.timedelta(hours=72)
    return render(request, "core/admin_dashboard.html", {
        "hostel_count": hostels.count(),
        "room_count": rooms.count(), "beds": _bed_summary(rooms),
        "pending_applications": RoomApplication.objects.filter(status=ApplicationStatus.PENDING).count(),
        "overdue_complaints": Complaint.objects.filter(
            room__hostel__is_active=True, status__in=["OPEN", "IN_PROGRESS"], created_at__lt=overdue,
        ).count(),
    })
