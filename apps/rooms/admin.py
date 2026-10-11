from django.contrib import admin

from .models import Hostel, Room


@admin.register(Hostel)
class HostelAdmin(admin.ModelAdmin):
    list_display = ("name", "gender_type", "is_active")
    filter_horizontal = ("wardens",)


@admin.register(Room)
class RoomAdmin(admin.ModelAdmin):
    list_display = ("room_no", "hostel", "floor", "room_type", "capacity", "occupancy", "annual_fee", "status")
    list_filter = ("hostel", "room_type", "status")
    search_fields = ("room_no",)
