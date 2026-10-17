from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Sum

from apps.allocation.models import Allocation
from apps.core.models import TimeStampedModel


class FeeRecord(TimeStampedModel):
    """FR-7.1: one fee record per allocation, equal to the room's annual fee."""
    allocation = models.OneToOneField(Allocation, on_delete=models.PROTECT, related_name="fee_record")
    academic_year = models.CharField(max_length=9, blank=True)
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
    receipt_no = models.CharField(max_length=15)
    amount = models.DecimalField(max_digits=9, decimal_places=2, validators=[MinValueValidator(0.01)])
    mode = models.CharField(max_length=6, choices=PaymentMode.choices)
    txn_reference = models.CharField(max_length=30, blank=True)
    paid_on = models.DateField()
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    # Generated when the payment form is rendered; stops a double click recording a payment twice (SAD 4.4.2)
    submission_id = models.CharField(max_length=36, null=True, blank=True)

    class Meta:
        ordering = ["-paid_on"]
        constraints = [
            models.UniqueConstraint(fields=["receipt_no"], name="uniq_receipt_no"),
            models.UniqueConstraint(fields=["submission_id"], name="uniq_payment_submission"),
            models.CheckConstraint(condition=models.Q(amount__gt=0), name="chk_payment_positive"),
        ]

    def __str__(self):
        return self.receipt_no
