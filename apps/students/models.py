from django.conf import settings
from django.core.validators import RegexValidator
from django.db import models

from apps.core.models import TimeStampedModel

mobile_validator = RegexValidator(r"^[6-9]\d{9}$", "Enter a valid 10-digit mobile number.")   # FR-2.3


class Gender(models.TextChoices):
    MALE = "M", "Male"
    FEMALE = "F", "Female"


class BloodGroup(models.TextChoices):
    A_POS = "A+", "A+"
    A_NEG = "A-", "A-"
    B_POS = "B+", "B+"
    B_NEG = "B-", "B-"
    AB_POS = "AB+", "AB+"
    AB_NEG = "AB-", "AB-"
    O_POS = "O+", "O+"
    O_NEG = "O-", "O-"


class MasterStudent(TimeStampedModel):
    """Student master list imported from the university (assumption A-1). Used to validate registration."""
    srn = models.CharField("SRN", max_length=13, unique=True)
    name = models.CharField(max_length=60)
    gender = models.CharField(max_length=1, choices=Gender.choices)
    program = models.CharField(max_length=30)
    year = models.PositiveSmallIntegerField()
    email = models.EmailField(unique=True)

    def __str__(self):
        return f"{self.srn} {self.name}"


class StudentProfile(TimeStampedModel):
    """Field layout: SRS Appendix B, Table B-1."""
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="student_profile")
    # Read-only for students (FR-2.2)
    srn = models.CharField("SRN", max_length=13, unique=True)
    name = models.CharField(max_length=60)
    gender = models.CharField(max_length=1, choices=Gender.choices)
    program = models.CharField(max_length=30)
    year = models.PositiveSmallIntegerField()
    # Editable by the student (FR-2.1)
    mobile = models.CharField(max_length=10, validators=[mobile_validator], blank=True)
    personal_email = models.EmailField(blank=True)
    permanent_address = models.CharField(max_length=250, blank=True)
    guardian_name = models.CharField(max_length=60, blank=True)
    guardian_relationship = models.CharField(max_length=20, blank=True)
    guardian_mobile = models.CharField(max_length=10, validators=[mobile_validator], blank=True)
    emergency_contact_name = models.CharField(max_length=60, blank=True)
    emergency_contact_mobile = models.CharField(max_length=10, validators=[mobile_validator], blank=True)
    blood_group = models.CharField(max_length=3, choices=BloodGroup.choices, blank=True)
    photo = models.ImageField(upload_to="photos/", blank=True)
    # BR-4: medical/disability priority, set by the Administrator only
    priority_flag = models.BooleanField(default=False)

    MANDATORY_FIELDS = ("mobile", "permanent_address", "guardian_name", "guardian_relationship",
                        "guardian_mobile", "blood_group")

    class Meta:
        ordering = ["srn"]

    def __str__(self):
        return f"{self.srn} {self.name}"

    @property
    def is_complete(self):
        """FR-2.4: all mandatory fields filled before applying for a room."""
        return all(getattr(self, f) for f in self.MANDATORY_FIELDS)
