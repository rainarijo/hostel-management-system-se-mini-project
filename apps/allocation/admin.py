from django.contrib import admin

from .models import Allocation, ApplicationWindow, AutoAllocateRun, RoomApplication, RoomChangeRequest

admin.site.register(ApplicationWindow)


@admin.register(RoomApplication)
class RoomApplicationAdmin(admin.ModelAdmin):
    list_display = ("__str__", "academic_year", "preference_1", "status", "submitted_at")
    list_filter = ("status", "academic_year")


@admin.register(Allocation)
class AllocationAdmin(admin.ModelAdmin):
    list_display = ("student", "room", "bed_no", "start_date", "end_date", "status")
    list_filter = ("status", "room__hostel")


admin.site.register(RoomChangeRequest)
admin.site.register(AutoAllocateRun)
