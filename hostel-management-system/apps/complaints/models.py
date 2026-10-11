from django.db import models

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

    def save(self, *args, **kwargs):
        if not self.complaint_no:
            from django.utils import timezone
            year = timezone.now().year
            count = Complaint.objects.filter(complaint_no__startswith=f"CMP-{year}-").count() + 1
            self.complaint_no = f"CMP-{year}-{count:05d}"
        super().save(*args, **kwargs)
