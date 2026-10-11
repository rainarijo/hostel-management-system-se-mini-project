from django.contrib import admin

from .models import Complaint


@admin.register(Complaint)
class ComplaintAdmin(admin.ModelAdmin):
    list_display = ("complaint_no", "student", "room", "category", "status", "created_at")
    list_filter = ("status", "category")
