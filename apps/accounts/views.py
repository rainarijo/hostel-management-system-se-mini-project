from django.contrib import messages
from django.contrib.auth import login, logout
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from apps.core.audit import log_action

from .forms import LoginForm


def login_view(request):
    if request.user.is_authenticated:
        return redirect("core:home")
    form = LoginForm(request, data=request.POST or None)
    if request.method == "POST" and form.is_valid():
        login(request, form.user)            # Django rotates the session id on login (SEC-REQ-5)
        log_action("LOGIN_SUCCESS", user=form.user, entity="user", entity_id=form.user.pk, request=request)
        return redirect(request.GET.get("next") or "core:home")
    return render(request, "accounts/login.html", {"form": form})


@require_POST
def logout_view(request):
    if request.user.is_authenticated:
        log_action("LOGOUT", user=request.user, entity="user", entity_id=request.user.pk, request=request)
    logout(request)                          # FR-1.7: invalidates the server-side session
    messages.info(request, "You have been logged out.")
    return redirect("accounts:login")


def register_view(request):
    """FR-1.1, FR-1.2: student self-registration against the master list. Sprint 1 story."""
    return render(request, "coming_soon.html", {"feature": "Student registration", "frs": "FR-1.1, FR-1.2"})


def password_reset_view(request):
    """FR-1.6: password reset by e-mail link. Sprint 1 story (use django.contrib.auth.views)."""
    return render(request, "coming_soon.html", {"feature": "Password reset", "frs": "FR-1.6"})
