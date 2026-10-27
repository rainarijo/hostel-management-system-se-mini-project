
from django.contrib import admin

from apps.accounts.models import Role
from .models import AuditLog


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = (
        "timestamp",
        "user",
        "action",
        "entity",
        "entity_id",
        "ip_address",
    )
    list_filter = ("action",)
    search_fields = ("user__email", "entity_id")
    readonly_fields = (
        "user",
        "action",
        "entity",
        "entity_id",
        "old_value",
        "new_value",
        "ip_address",
        "timestamp",
    )

    def has_view_permission(self, request, obj=None):
        return (
            request.user.is_active
            and request.user.is_staff
            and request.user.is_superuser
            and getattr(request.user, "role", None) == Role.ADMIN
        )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
