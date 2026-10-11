"""Role-based access control helpers (FR-1.4, BR-1, SEC-REQ-4).

Usage:
    @role_required(Role.WARDEN, Role.ADMIN)
    def my_view(request): ...
"""
from functools import wraps

from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied

from apps.core.audit import log_action


def role_required(*roles):
    def decorator(view):
        @wraps(view)
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect_to_login(request.get_full_path())
            if request.user.role not in roles:
                log_action("ACCESS_DENIED", user=request.user, entity="url",
                           entity_id=request.path[:50], request=request)
                raise PermissionDenied
            return view(request, *args, **kwargs)
        return wrapper
    return decorator
