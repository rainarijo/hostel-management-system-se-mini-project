from django.db import models, transaction

from apps.core.models import TimeStampedModel
from apps.rooms.models import Room
from apps.students.models import StudentProfile


class ComplaintCategory(models.TextChoices):
    ELECTRICAL = "ELECTRICAL", "Electrical"
    PLUMBING = "PLUMBING", "Plumbing"
    FURNITURE = "FURNITURE", "Furniture"
    CLEANLINESS = "CLEANLINESS", "Cleanliness"
    INTERNET = "INTERNET", "Internet"
    OTHER = "OTHER", "Other"


class ComplaintStatus(models.TextChoices):
    OPEN = "OPEN", "Open"
    IN_PROGRESS = "IN_PROGRESS", "In Progress"
    RESOLVED = "RESOLVED", "Resolved"
    REJECTED = "REJECTED", "Rejected"


class Complaint(TimeStampedModel):
    """Field layout: SRS Appendix B, Table B-4."""
    complaint_no = models.CharField(max_length=14, unique=True, editable=False)   # CMP-YYYY-NNNNN (FR-6.2)
    student = models.ForeignKey(StudentProfile, on_delete=models.PROTECT, related_name="complaints")
    room = models.ForeignKey(Room, on_delete=models.PROTECT, related_name="complaints")
    category = models.CharField(max_length=12, choices=ComplaintCategory.choices)
    description = models.CharField(max_length=500)
    photo = models.ImageField(upload_to="complaints/", blank=True)
    status = models.CharField(max_length=12, choices=ComplaintStatus.choices, default=ComplaintStatus.OPEN)
    remark = models.CharField(max_length=300, blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.complaint_no or "New complaint"

    @property
    def hostel(self):
        """FR-6.2: the hostel is taken from the room, so it cannot disagree with it."""
        return self.room.hostel

    def save(self, *args, **kwargs):
        if not self.complaint_no:
            # Gap-free number from DocumentSequence (SAD 4.1.2, ADR-8). The number and the row are saved
            # in one transaction, so a failed save does not use up a number.
            from apps.core.sequences import next_number
            with transaction.atomic():
                self.complaint_no = next_number("CMP")
                super().save(*args, **kwargs)
            return
        super().save(*args, **kwargs)
