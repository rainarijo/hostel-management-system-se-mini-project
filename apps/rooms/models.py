from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from apps.core.models import TimeStampedModel
from apps.students.models import Gender


class Hostel(TimeStampedModel):
    name = models.CharField(max_length=60, unique=True)
    gender_type = models.CharField(max_length=1, choices=Gender.choices)        # BR-2
    wardens = models.ManyToManyField(settings.AUTH_USER_MODEL, related_name="hostels", blank=True,
                                     limit_choices_to={"role": "WARDEN"})
    is_active = models.BooleanField(default=True)                               # soft delete (FR-3.5)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class RoomType(models.TextChoices):
    SINGLE = "SINGLE", "Single"
    DOUBLE = "DOUBLE", "Double"
    TRIPLE = "TRIPLE", "Triple"


class RoomStatus(models.TextChoices):
    AVAILABLE = "AVAILABLE", "Available"
    FULL = "FULL", "Full"
    MAINTENANCE = "MAINTENANCE", "Under Maintenance"


class Room(TimeStampedModel):
    """Field layout: SRS Appendix B, Table B-2."""
    hostel = models.ForeignKey(Hostel, on_delete=models.PROTECT, related_name="rooms")
    room_no = models.CharField(max_length=10)
    floor = models.PositiveSmallIntegerField(validators=[MaxValueValidator(20)])
    room_type = models.CharField(max_length=10, choices=RoomType.choices)
    capacity = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(4)])
    annual_fee = models.DecimalField(max_digits=9, decimal_places=2,
                                     validators=[MinValueValidator(0), MaxValueValidator(500000)])
    status = models.CharField(max_length=12, choices=RoomStatus.choices, default=RoomStatus.AVAILABLE)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["hostel", "floor", "room_no"]
        constraints = [
            models.UniqueConstraint(fields=["hostel", "room_no"], name="uniq_room_no_per_hostel"),
            models.CheckConstraint(
                condition=models.Q(floor__gte=0, floor__lte=20, capacity__gte=1, capacity__lte=4,
                                   annual_fee__gte=0, annual_fee__lte=500000),
                name="chk_room_ranges"),
        ]

    def __str__(self):
        return f"{self.hostel.name} - {self.room_no}"

    @property
    def occupancy(self):
        """FR-3.3: number of active allocations."""
        from apps.allocation.models import Allocation
        return Allocation.objects.active().filter(room=self).count()

    @property
    def vacant_beds(self):
        return self.capacity - self.occupancy

    def refresh_status(self):
        """FR-3.3: Full when occupancy == capacity; Available when a bed is released (unless Under Maintenance)."""
        if self.status == RoomStatus.MAINTENANCE:
            return
        new = RoomStatus.FULL if self.occupancy >= self.capacity else RoomStatus.AVAILABLE
        if new != self.status:
            self.status = new
            self.save(update_fields=["status", "updated_at"])
