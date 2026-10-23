from django.contrib import admin
from django import forms
from django.core.exceptions import ValidationError

from apps.core.audit import log_action
from apps.rooms.validators import validate_allocation_room
from .models import Allocation, ApplicationWindow, AutoAllocateRun, RoomApplication, RoomChangeRequest

admin.site.register(ApplicationWindow)


@admin.register(RoomApplication)
class RoomApplicationAdmin(admin.ModelAdmin):
    list_display = ("__str__", "academic_year", "preference_1", "status", "submitted_at")
    list_filter = ("status", "academic_year")


class AllocationAdminForm(forms.ModelForm):
    class Meta:
        model = Allocation
        fields = "__all__"

    def clean(self):
        cleaned_data = super().clean()
        room = cleaned_data.get("room")
        if room is not None:
            try:
                validate_allocation_room(
                    room,
                    allocation=self.instance,
                    status=cleaned_data.get("status"),
                    bed_no=cleaned_data.get("bed_no"),
                )
            except ValidationError as error:
                self.add_error("room", error)
        return cleaned_data


@admin.register(Allocation)
class AllocationAdmin(admin.ModelAdmin):
    form = AllocationAdminForm
    list_display = ("student", "room", "bed_no", "start_date", "end_date", "status")
    list_filter = ("status", "room__hostel")

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        if not change:
            log_action(
                "ALLOCATION_CREATED",
                user=request.user,
                entity="allocation",
                entity_id=obj.pk,
                new=f"{obj.room} bed {obj.bed_no} {obj.get_status_display()}",
                request=request,
            )

    def has_delete_permission(self, request, obj=None):
        return False


admin.site.register(RoomChangeRequest)
admin.site.register(AutoAllocateRun)
