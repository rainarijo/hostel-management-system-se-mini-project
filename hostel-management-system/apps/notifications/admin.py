from django.contrib import admin

from .models import Announcement, EmailLog

admin.site.register(Announcement)


@admin.register(EmailLog)
class EmailLogAdmin(admin.ModelAdmin):
    list_display = ("created_at", "event", "to_email", "attempts", "sent")
