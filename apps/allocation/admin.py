from django import forms
from django.contrib import admin
from django.core.exceptions import ValidationError

from apps.core.audit import log_action

from .models import ACTIVE_STATUSES, Allocation, ApplicationWindow, AutoAllocateRun, RoomApplication
from .models import RoomChangeRequest
from .services import validate_allocation_room

admin.site.register(ApplicationWindow)


@admin.register(RoomApplication)
class RoomApplicationAdmin(admin.ModelAdmin):
    list_display = ("__str__", "academic_year", "preference_1", "status", "submitted_at")
    list_filter = ("status", "academic_year")


@admin.register(Allocation)
class AllocationAdmin(admin.ModelAdmin):
    class AllocationForm(forms.ModelForm):
        class Meta:
            model = Allocation
            fields = "__all__"

        def clean(self):
            cleaned = super().clean()
            room = cleaned.get("room")
            status = cleaned.get("status")
            if room is not None and status in ACTIVE_STATUSES:
                try:
                    validate_allocation_room(
                        room, allocation=self.instance, status=status, bed_no=cleaned.get("bed_no"))
                except ValidationError as exc:
                    raise forms.ValidationError(exc.messages) from exc
            return cleaned

    list_display = ("student", "room", "bed_no", "start_date", "end_date", "status")
    list_filter = ("status", "room__hostel")
    form = AllocationForm

    @staticmethod
    def _audit_value(allocation):
        return (f"Student: {allocation.student.srn}; room: {allocation.room}; bed: {allocation.bed_no}; "
                f"status: {allocation.get_status_display()}; start: {allocation.start_date}; "
                f"end: {allocation.end_date or '-'}")

    def save_model(self, request, obj, form, change):
        old = self._audit_value(Allocation.objects.select_related("student", "room").get(pk=obj.pk)) if change else ""
        super().save_model(request, obj, form, change)
        log_action("ALLOCATION_UPDATED" if change else "ALLOCATION_CREATED", user=request.user,
                   entity="allocation", entity_id=obj.pk, old=old, new=self._audit_value(obj), request=request)

    def has_delete_permission(self, request, obj=None):
        return False


admin.site.register(RoomChangeRequest)
admin.site.register(AutoAllocateRun)
