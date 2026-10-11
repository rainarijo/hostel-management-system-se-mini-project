from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Sum

from apps.allocation.models import Allocation
from apps.core.models import TimeStampedModel


class FeeRecord(TimeStampedModel):
    """FR-7.1: one fee record per allocation, equal to the room's annual fee."""
    allocation = models.OneToOneField(Allocation, on_delete=models.PROTECT, related_name="fee_record")
    total_amount = models.DecimalField(max_digits=9, decimal_places=2)

    def __str__(self):
        return f"Fee for {self.allocation}"

    @property
    def amount_paid(self):
        return self.payments.aggregate(s=Sum("amount"))["s"] or 0

    @property
    def balance(self):
        return self.total_amount - self.amount_paid

    @property
    def is_paid(self):
        return self.balance <= 0


class PaymentMode(models.TextChoices):
    ONLINE = "ONLINE", "Online transfer"
    DD = "DD", "Demand draft"
    CASH = "CASH", "Cash"


class Payment(TimeStampedModel):
    """Field layout: SRS Appendix B, Table B-5."""
    fee_record = models.ForeignKey(FeeRecord, on_delete=models.PROTECT, related_name="payments")
    receipt_no = models.CharField(max_length=15, unique=True)
    amount = models.DecimalField(max_digits=9, decimal_places=2, validators=[MinValueValidator(0.01)])
    mode = models.CharField(max_length=6, choices=PaymentMode.choices)
    txn_reference = models.CharField(max_length=30, blank=True)
    paid_on = models.DateField()
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)

    class Meta:
        ordering = ["-paid_on"]

    def __str__(self):
        return self.receipt_no
