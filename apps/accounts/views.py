
import hashlib
import secrets
from datetime import timedelta

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login, logout
from django.core.mail import send_mail
from django.db import transaction
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST


from apps.core.permissions import role_required

from .models import Role
from apps.core.audit import log_action
from apps.students.models import StudentProfile

from .forms import LoginForm, RegistrationForm
from .models import AuthToken, TokenPurpose, User


def login_view(request):
    if request.user.is_authenticated:
        return redirect("core:home")

    form = LoginForm(request, data=request.POST or None)
    if request.method == "POST" and form.is_valid():
        login(request, form.user)
        log_action(
            "LOGIN_SUCCESS",
            user=form.user,
            entity="user",
            entity_id=form.user.pk,
            request=request,
        )
        return redirect(request.GET.get("next") or "core:home")

    return render(request, "accounts/login.html", {"form": form})


@require_POST
def logout_view(request):
    if request.user.is_authenticated:
        log_action(
            "LOGOUT",
            user=request.user,
            entity="user",
            entity_id=request.user.pk,
            request=request,
        )
    logout(request)
    messages.info(request, "You have been logged out.")
    return redirect("accounts:login")


def register_view(request):
    if request.user.is_authenticated:
        return redirect("core:home")

    form = RegistrationForm(request.POST or None)

    if request.method == "POST" and form.is_valid():
        master = form.master_student
        raw_token = secrets.token_urlsafe(32)

        try:
            with transaction.atomic():
                # Recheck eligibility inside the transaction.
                if (
                    User.objects.filter(email__iexact=master.email).exists()
                    or StudentProfile.objects.filter(
                        srn__iexact=master.srn
                    ).exists()
                ):
                    form.add_error(
                        None,
                        "SRN not found or already registered",
                    )
                    return render(
                        request,
                        "accounts/register.html",
                        {"form": form},
                    )

                user = User.objects.create_user(
                    email=master.email.lower(),
                    password=form.cleaned_data["password1"],
                    first_name=master.name,
                    is_active=False,
                )

                StudentProfile.objects.create(
                    user=user,
                    srn=master.srn,
                    name=master.name,
                    gender=master.gender,
                    program=master.program,
                    year=master.year,
                )

                AuthToken.objects.create(
                    user=user,
                    purpose=TokenPurpose.VERIFY,
                    token_hash=hashlib.sha256(
                        raw_token.encode("utf-8")
                    ).hexdigest(),
                    expires_at=timezone.now() + timedelta(hours=24),
                )

        except Exception:
            # Keep unexpected database errors visible during development.
            raise

        verification_url = request.build_absolute_uri(
            reverse("accounts:verify_email", args=[raw_token])
        )
        send_mail(
            subject="Verify your Hostel Management System account",
            message=(
                f"Hello {master.name},\n\n"
                "Please verify your account using this link:\n"
                f"{verification_url}\n\n"
                "This link expires in 24 hours."
            ),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[master.email],
            fail_silently=False,
        )

        messages.success(
            request,
            "Registration successful. Check your institutional email "
            "for the verification link.",
        )
        return redirect("accounts:login")

    return render(request, "accounts/register.html", {"form": form})


@require_GET
def verify_email_view(request, token):
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()

    with transaction.atomic():
        auth_token = (
            AuthToken.objects.select_for_update()
            .select_related("user")
            .filter(
                token_hash=token_hash,
                purpose=TokenPurpose.VERIFY,
                used_at__isnull=True,
                expires_at__gt=timezone.now(),
            )
            .first()
        )

        if auth_token is None:
            messages.error(
                request,
                "This verification link is invalid or has expired.",
            )
            return redirect("accounts:login")

        user = auth_token.user
        user.is_active = True
        user.save(update_fields=["is_active"])

        auth_token.used_at = timezone.now()
        auth_token.save(update_fields=["used_at"])

    messages.success(
        request,
        "Your email has been verified. You can now log in.",
    )
    return redirect("accounts:login")


def password_reset_view(request):
    """FR-1.6: password reset by e-mail link. Sprint 1 story."""
    return render(
        request,
        "coming_soon.html",
        {"feature": "Password reset", "frs": "FR-1.6"},
    )


@role_required(Role.ADMIN)
def account_list_view(request):
    users = User.objects.all().order_by("email")

    return render(
        request,
        "accounts/account_list.html",
        {
            "users": users,
            "role_choices": Role.choices,
        },
    )


@role_required(Role.ADMIN)
def account_create_view(request):
    from .forms import AdminAccountCreateForm

    form = AdminAccountCreateForm(request.POST or None)

    if request.method == "POST" and form.is_valid():
        user = User.objects.create_user(
            email=form.cleaned_data["email"],
            password=form.cleaned_data["password1"],
            first_name=form.cleaned_data["first_name"],
            last_name=form.cleaned_data["last_name"],
            role=form.cleaned_data["role"],
            is_active=True,
        )
        log_action(
            "ACCOUNT_CREATED",
            user=request.user,
            entity="user",
            entity_id=user.pk,
            new=f"{user.email}:{user.role}",
            request=request,
        )
        messages.success(request, "Account created successfully.")
        return redirect("accounts:account_list")

    return render(
        request,
        "accounts/account_form.html",
        {"form": form},
    )


@require_POST
@role_required(Role.ADMIN)
def account_change_role_view(request, user_id):
    target = User.objects.filter(pk=user_id).first()
    if target is None:
        from django.http import Http404
        raise Http404

    new_role = request.POST.get("role")
    allowed_roles = {Role.STUDENT, Role.WARDEN, Role.ADMIN}

    if new_role not in allowed_roles:
        messages.error(request, "Invalid role.")
        return redirect("accounts:account_list")

    old_role = target.role

    if target.role == Role.ADMIN and new_role != Role.ADMIN:
        other_active_admins = User.objects.filter(
            role=Role.ADMIN,
            is_active=True,
        ).exclude(pk=target.pk).count()
        if target.is_active and other_active_admins == 0:
            messages.error(
                request,
                "The last active administrator cannot be demoted.",
            )
            return redirect("accounts:account_list")

    target.role = new_role
    target.save(update_fields=["role"])

    log_action(
        "ACCOUNT_ROLE_CHANGED",
        user=request.user,
        entity="user",
        entity_id=target.pk,
        old=old_role,
        new=new_role,
        request=request,
    )
    messages.success(request, "Account role updated.")
    return redirect("accounts:account_list")


@require_POST
@role_required(Role.ADMIN)
def account_deactivate_view(request, user_id):
    target = User.objects.filter(pk=user_id).first()
    if target is None:
        from django.http import Http404
        raise Http404

    if target.pk == request.user.pk:
        messages.error(request, "You cannot deactivate your own account.")
        return redirect("accounts:account_list")

    if target.role == Role.ADMIN and target.is_active:
        other_active_admins = User.objects.filter(
            role=Role.ADMIN,
            is_active=True,
        ).exclude(pk=target.pk).count()
        if other_active_admins == 0:
            messages.error(
                request,
                "The last active administrator cannot be deactivated.",
            )
            return redirect("accounts:account_list")

    target.is_active = False
    target.save(update_fields=["is_active"])

    log_action(
        "ACCOUNT_DEACTIVATED",
        user=request.user,
        entity="user",
        entity_id=target.pk,
        old="active",
        new="inactive",
        request=request,
    )
    messages.success(request, "Account deactivated.")
    return redirect("accounts:account_list")
