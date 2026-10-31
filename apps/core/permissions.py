"""Role-based access control helpers (FR-1.4, BR-1, SEC-REQ-4).

Usage:
    @role_required(Role.WARDEN, Role.ADMIN)
    def my_view(request): ...

role_required is also the central place where denials are logged as security events (SAD 3.9, 4.4.1):
a role denial (403), and any 403/404 the view produces for an object outside the user's scope, whether it
raises PermissionDenied/Http404, lets AccessDenied/ObjectNotFound escape, or returns a 403/404 response.
"""
import logging
from functools import wraps

from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied
from django.http import Http404

from apps.core.audit import log_action
from apps.core.exceptions import AccessDenied, ObjectNotFound

security_logger = logging.getLogger("hms.security")

ROLE_DENIED = "role_denied"
FORBIDDEN = "forbidden"
NOT_FOUND = "not_found"


def _safe_path(request):
    """request.path with secret URL parts (e.g. <token>) replaced. Never the query string or body."""
    path = request.path
    match = getattr(request, "resolver_match", None)
    for name, value in (match.kwargs.items() if match else ()):
        if "token" in name.lower() and value:
            path = path.replace(str(value), "<redacted>")
    return path


def log_security_event(request, event, reason):
    """WARNING on 'hms.security'. Users are identified by id only: no e-mail, password, token, session or body."""
    user = getattr(request, "user", None)
    user_id = user.pk if user is not None and user.is_authenticated else None
    path = _safe_path(request)
    security_logger.warning(
        "security_event=%s user_id=%s method=%s path=%s reason=%s", event, user_id, request.method, path, reason,
        extra={"security_event": event, "user_id": user_id, "method": request.method, "path": path,
               "reason": reason},
    )


def role_required(*roles):
    allowed = ",".join(str(r) for r in roles)

    def decorator(view):
        @wraps(view)
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect_to_login(request.get_full_path())
            if request.user.role not in roles:
                log_action("ACCESS_DENIED", user=request.user, entity="url",
                           entity_id=request.path[:50], request=request)
                log_security_event(request, ROLE_DENIED, f"role {request.user.role} not in {allowed}")
                raise PermissionDenied
            try:
                response = view(request, *args, **kwargs)
            except (PermissionDenied, AccessDenied) as exc:
                log_security_event(request, FORBIDDEN, "denied by object or scope check")
                if isinstance(exc, AccessDenied):
                    raise PermissionDenied from exc
                raise
            except (Http404, ObjectNotFound) as exc:
                log_security_event(request, NOT_FOUND, "object not found or outside the user's scope")
                if isinstance(exc, ObjectNotFound):
                    raise Http404 from exc
                raise
            status = getattr(response, "status_code", None)
            if status == 403:
                log_security_event(request, FORBIDDEN, "view returned 403")
            elif status == 404:
                log_security_event(request, NOT_FOUND, "view returned 404")
            return response
        return wrapper
    return decorator
