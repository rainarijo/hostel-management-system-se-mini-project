from django.db import models
from django.db.models import Q

from apps.core.models import TimeStampedModel
from apps.rooms.models import Room, RoomType
from apps.students.models import StudentProfile


class ApplicationWindow(TimeStampedModel):
    """FR-4.1: one window per academic year, e.g. '2026-2027'."""
    academic_year = models.CharField(max_length=9, unique=True)
    start_date = models.DateField()
    end_date = models.DateField()

    def __str__(self):
        return f"{self.academic_year}: {self.start_date:%d-%m-%Y} to {self.end_date:%d-%m-%Y}"


class ApplicationStatus(models.TextChoices):
    PENDING = "PENDING", "Pending"
    ALLOCATED = "ALLOCATED", "Allocated"
    REJECTED = "REJECTED", "Rejected"
    WITHDRAWN = "WITHDRAWN", "Withdrawn"


class RoomApplication(TimeStampedModel):
    """Field layout: SRS Appendix B, Table B-3."""
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
            models.UniqueConstraint(fields=["student", "academic_year"], name="one_application_per_year"),
        ]

    def __str__(self):
        return f"APP-{self.pk:05d} {self.student.srn}" if self.pk else "New application"


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
                                    name="one_active_allocation_per_bed"),
            models.UniqueConstraint(fields=["student"], condition=Q(status__in=ACTIVE_STATUSES),
                                    name="one_active_allocation_per_student"),
        ]

    def __str__(self):
        return f"{self.student.srn} -> {self.room} bed {self.bed_no} ({self.get_status_display()})"


class RoomChangeRequest(TimeStampedModel):
    """FR-5.1 - FR-5.3."""
    allocation = models.ForeignKey(Allocation, on_delete=models.PROTECT, related_name="change_requests")
    reason = models.CharField(max_length=300)
    status = models.CharField(max_length=10, choices=ApplicationStatus.choices, default=ApplicationStatus.PENDING)
    decision_remark = models.CharField(max_length=300, blank=True)

    def __str__(self):
        return f"Change request {self.pk} for {self.allocation.student.srn}"
