
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Prefetch
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from apps.accounts.models import Role
from apps.core.audit import log_action
from apps.core.permissions import role_required
from django.db.models import Q

from apps.allocation.models import Allocation, AllocationStatus
from apps.rooms.models import Hostel
from .forms import StudentProfileForm
from .models import StudentProfile


@login_required
@role_required(Role.STUDENT, Role.WARDEN, Role.ADMIN)
def index(request):
    """Display a student's profile or the administrator's profile list."""
    if request.user.role == Role.STUDENT:
        profile = get_object_or_404(
            StudentProfile,
            user=request.user,
        )
        return redirect("students:profile_detail", profile_id=profile.pk)

    if request.user.role == Role.ADMIN:
        profiles = Paginator(
            StudentProfile.objects.only("id", "srn", "name", "program", "year"),
            50,
        ).get_page(request.GET.get("page"))
        return render(
            request,
            "students/profile_list.html",
            {"profiles": profiles},
        )

    # Warden profile-list access is outside Issue #22's scope.
    return render(request, "coming_soon.html", {
        "feature": "Student profiles",
        "frs": "FR-2.1 - FR-2.2",
    })


@login_required
@role_required(Role.WARDEN, Role.ADMIN)
def search(request):
    """FR-2.5, FR-2.6: search within the actor's authorized scope."""
    query = request.GET.get("q", "").strip()
    hostel_id = request.GET.get("hostel", "").strip()
    room_no = request.GET.get("room", "").strip()
    year = request.GET.get("year", "").strip()

    if request.user.role == Role.WARDEN:
        hostels = request.user.hostels.filter(is_active=True)
    else:
        hostels = Hostel.objects.filter(is_active=True)

    allocations = Allocation.objects.filter(
        room__hostel__in=hostels,
        status__in=[
            AllocationStatus.PROVISIONAL,
            AllocationStatus.CONFIRMED,
        ],
    ).select_related("room", "room__hostel")

    if hostel_id:
        if not hostel_id.isdigit():
            allocations = allocations.none()
        else:
            allocations = allocations.filter(
                room__hostel_id=int(hostel_id)
            )

    if room_no:
        allocations = allocations.filter(
            room__room_no__icontains=room_no
        )

    profiles = StudentProfile.objects.all()

    if request.user.role == Role.WARDEN or hostel_id or room_no:
        profiles = profiles.filter(
            pk__in=allocations.values("student_id")
        )

    if query:
        profiles = profiles.filter(
            Q(srn__icontains=query) | Q(name__icontains=query)
        )

    if year.isdigit():
        profiles = profiles.filter(year=int(year))

    profiles = profiles.distinct().order_by("srn").prefetch_related(
        Prefetch("allocations", queryset=allocations, to_attr="search_allocations")
    )

    page = Paginator(profiles, 50).get_page(request.GET.get("page"))
    results = [
        {
            "profile": profile,
            "allocations": profile.search_allocations,
        }
        for profile in page
    ]
    filters = request.GET.copy()
    filters.pop("page", None)

    return render(
        request,
        "students/search.html",
        {
            "results": results,
            "page": page,
            "filters": filters.urlencode(),
            "query": query,
            "hostels": hostels,
            "selected_hostel": hostel_id,
            "room_no": room_no,
            "year": year,
        },
    )


@login_required
@role_required(Role.STUDENT, Role.ADMIN)
def profile_detail(request, profile_id):
    profile = get_object_or_404(StudentProfile, pk=profile_id)

    if request.user.role == Role.STUDENT and profile.user_id != request.user.pk:
        from django.core.exceptions import PermissionDenied
        raise PermissionDenied

    return render(
        request,
        "students/profile_detail.html",
        {"profile": profile},
    )


@login_required
@role_required(Role.STUDENT, Role.ADMIN)
@require_http_methods(["GET", "POST"])
def profile_edit(request, profile_id):
    profile = get_object_or_404(StudentProfile, pk=profile_id)

    is_admin = request.user.role == Role.ADMIN

    if not is_admin and profile.user_id != request.user.pk:
        from django.core.exceptions import PermissionDenied
        raise PermissionDenied

    old_values = {
        field: str(getattr(profile, field))
        for field in (
            "mobile",
            "personal_email",
            "permanent_address",
            "guardian_name",
            "guardian_relationship",
            "guardian_mobile",
            "emergency_contact_name",
            "emergency_contact_mobile",
            "blood_group",
            "photo",
            "srn",
            "name",
            "gender",
            "program",
            "year",
        )
    }

    form = StudentProfileForm(
        request.POST or None,
        request.FILES or None,
        instance=profile,
        is_admin=is_admin,
    )

    sensitive_profile_fields = {
        "mobile",
        "personal_email",
        "permanent_address",
        "guardian_name",
        "guardian_mobile",
        "emergency_contact_name",
        "emergency_contact_mobile",
        "srn",
    }

    if request.method == "POST" and form.is_valid():
        updated_profile = form.save()

        changed_fields = [
            field
            for field, old_value in old_values.items()
            if str(getattr(updated_profile, field)) != old_value
        ]

        sensitive_profile_fields = {
            "mobile",
            "personal_email",
            "permanent_address",
            "guardian_name",
            "guardian_mobile",
            "emergency_contact_name",
            "emergency_contact_mobile",
            "srn",
        }

        for field in changed_fields:
            old_value = old_values[field]
            new_value = str(getattr(updated_profile, field))

            if field == "photo":
                old_value = "[photo set]" if old_value else "[no photo]"
                new_value = "[photo set]" if new_value else "[no photo]"
            elif field in sensitive_profile_fields:
                old_value = "[redacted]"
                new_value = "[redacted]"

            log_action(
                "STUDENT_PROFILE_FIELD_UPDATED",
                user=request.user,
                entity="student_profile",
                entity_id=profile.pk,
                old=f"{field}: {old_value}",
                new=f"{field}: {new_value}",
                request=request,
            )

        messages.success(request, "Profile updated successfully.")
        return redirect(
            "students:profile_detail",
            profile_id=profile.pk,
        )

    return render(
        request,
        "students/profile_form.html",
        {"form": form, "profile": profile},
    )
