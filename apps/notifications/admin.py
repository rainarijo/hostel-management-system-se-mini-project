from django.contrib import admin

from .models import Announcement, EmailLog, NotificationOutbox

admin.site.register(Announcement)


@admin.register(EmailLog)
class EmailLogAdmin(admin.ModelAdmin):
    list_display = ("created_at", "event", "to_email", "attempts", "sent")


@admin.register(NotificationOutbox)
class NotificationOutboxAdmin(admin.ModelAdmin):
    list_display = ("created_at", "kind", "recipient_email", "status", "attempts")
    list_filter = ("status", "kind")
