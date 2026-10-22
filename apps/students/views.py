
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from apps.accounts.models import Role
from apps.core.audit import log_action
from apps.core.permissions import role_required

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
        profiles = StudentProfile.objects.select_related("user").all()
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

    if request.method == "POST" and form.is_valid():
        updated_profile = form.save()

        changed_fields = [
            field
            for field, old_value in old_values.items()
            if str(getattr(updated_profile, field)) != old_value
        ]

        log_action(
            "STUDENT_PROFILE_UPDATED",
            user=request.user,
            entity="student_profile",
            entity_id=profile.pk,
            old=", ".join(changed_fields),
            new=", ".join(changed_fields),
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
