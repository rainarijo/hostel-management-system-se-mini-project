from django.conf import settings
from django.db import models
from django.db.models import Q

from apps.core.models import TimeStampedModel
from apps.rooms.models import Room, RoomType
from apps.students.models import StudentProfile


class ApplicationWindow(TimeStampedModel):
    """FR-4.1: one window per academic year, e.g. '2026-2027'."""
    academic_year = models.CharField(max_length=9)
    start_date = models.DateField()
    end_date = models.DateField()
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["academic_year"], name="uniq_window_per_year")]

    def __str__(self):
        return f"{self.academic_year}: {self.start_date:%d-%m-%Y} to {self.end_date:%d-%m-%Y}"


class ApplicationStatus(models.TextChoices):
    PENDING = "PENDING", "Pending"
    ALLOCATED = "ALLOCATED", "Allocated"
    REJECTED = "REJECTED", "Rejected"
    WITHDRAWN = "WITHDRAWN", "Withdrawn"


class RoomApplication(TimeStampedModel):
    """Field layout: SRS Appendix B, Table B-3."""
    # APP-YYYY-NNNNN
    application_no = models.CharField(max_length=15, unique=True, null=True, blank=True, editable=False)
    student = models.ForeignKey(StudentProfile, on_delete=models.PROTECT, related_name="applications")
    academic_year = models.CharField(max_length=9)
    preference_1 = models.CharField(max_length=10, choices=RoomType.choices)
    preference_2 = models.CharField(max_length=10, choices=RoomType.choices, blank=True)
    preference_3 = models.CharField(max_length=10, choices=RoomType.choices, blank=True)
    preferred_roommate_srn = models.CharField(max_length=13, blank=True)
    status = models.CharField(max_length=10, choices=ApplicationStatus.choices, default=ApplicationStatus.PENDING)
    rejection_reason = models.CharField(max_length=300, blank=True)
    submitted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["submitted_at"]
        constraints = [  # BR-3 / FR-4.3: one application per student per academic year
            models.UniqueConstraint(fields=["student", "academic_year"], name="uniq_application_per_year"),
        ]

    def __str__(self):
        return f"{self.application_no or 'New application'} {self.student.srn}"


class AllocationStatus(models.TextChoices):
    PROVISIONAL = "PROVISIONAL", "Provisional"
    CONFIRMED = "CONFIRMED", "Confirmed"
    ENDED = "ENDED", "Ended"
    CANCELLED = "CANCELLED", "Cancelled"


ACTIVE_STATUSES = [AllocationStatus.PROVISIONAL, AllocationStatus.CONFIRMED]


class AllocationQuerySet(models.QuerySet):
    def active(self):
        return self.filter(status__in=ACTIVE_STATUSES)


class Allocation(TimeStampedModel):
    student = models.ForeignKey(StudentProfile, on_delete=models.PROTECT, related_name="allocations")
    room = models.ForeignKey(Room, on_delete=models.PROTECT, related_name="allocations")
    bed_no = models.PositiveSmallIntegerField()
    academic_year = models.CharField(max_length=9, blank=True)
    application = models.ForeignKey(RoomApplication, null=True, blank=True, on_delete=models.SET_NULL)
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=12, choices=AllocationStatus.choices, default=AllocationStatus.PROVISIONAL)
    end_reason = models.CharField(max_length=300, blank=True)

    objects = AllocationQuerySet.as_manager()

    class Meta:
        ordering = ["-start_date"]
        constraints = [
            # FR-4.6: enforced by the database, so concurrent requests cannot double-allocate.
            models.UniqueConstraint(fields=["room", "bed_no"], condition=Q(status__in=ACTIVE_STATUSES),
                                    name="uniq_active_bed"),
            models.CheckConstraint(condition=Q(bed_no__gte=1), name="chk_bed_no_positive"),
            models.UniqueConstraint(fields=["student"], condition=Q(status__in=ACTIVE_STATUSES),
                                    name="uniq_active_allocation_per_student"),
        ]

    def __str__(self):
        return f"{self.student.srn} -> {self.room} bed {self.bed_no} ({self.get_status_display()})"


class ChangeStatus(models.TextChoices):
    PENDING = "PENDING", "Pending"
    APPROVED = "APPROVED", "Approved"
    REJECTED = "REJECTED", "Rejected"


class RoomChangeRequest(TimeStampedModel):
    """FR-5.1 - FR-5.3."""
    student = models.ForeignKey(StudentProfile, on_delete=models.PROTECT, related_name="change_requests")
    from_allocation = models.ForeignKey(Allocation, on_delete=models.PROTECT, related_name="change_requests")
    reason = models.CharField(max_length=300)
    status = models.CharField(max_length=10, choices=ChangeStatus.choices, default=ChangeStatus.PENDING)
    decision_reason = models.CharField(max_length=300, blank=True)
    decided_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)

    class Meta:
        constraints = [  # FR-5.1: one pending request per student
            models.UniqueConstraint(fields=["student"], condition=Q(status="PENDING"),
                                    name="uniq_pending_change_per_student"),
        ]

    def __str__(self):
        return f"Change request {self.pk} for {self.student.srn}"


class RunStatus(models.TextChoices):
    RUNNING = "RUNNING", "Running"
    DONE = "DONE", "Done"
    FAILED = "FAILED", "Failed"


class AutoAllocateRun(models.Model):
    """FR-4.7: one row per Auto-Allocate run; the constraint stops two simultaneous runs for a hostel."""
    hostel = models.ForeignKey("rooms.Hostel", on_delete=models.PROTECT, related_name="auto_runs")
    started_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    started_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=7, choices=RunStatus.choices, default=RunStatus.RUNNING)
    allocated_count = models.PositiveIntegerField(default=0)
    unallocated_count = models.PositiveIntegerField(default=0)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["hostel"], condition=Q(status="RUNNING"),
                                    name="uniq_running_autoalloc_per_hostel"),
        ]
