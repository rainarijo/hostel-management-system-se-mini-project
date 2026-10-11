from .models import AuditLog


def client_ip(request):
    if request is None:
        return None
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
    return forwarded.split(",")[0].strip() if forwarded else request.META.get("REMOTE_ADDR")


def log_action(action, user=None, entity="", entity_id="", old="", new="", request=None):
    """Record one audit entry. Use this from every feature that changes data."""
    return AuditLog.objects.create(
        user=user if (user is not None and user.is_authenticated) else None,
        action=action, entity=entity, entity_id=str(entity_id or ""),
        old_value=str(old or ""), new_value=str(new or ""), ip_address=client_ip(request),
    )
