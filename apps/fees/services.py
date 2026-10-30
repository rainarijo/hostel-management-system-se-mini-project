from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from apps.accounts.models import Role
from apps.allocation.models import Allocation, AllocationStatus
from apps.allocation.services import confirm as confirm_allocation
from apps.core.audit import log_action
from apps.core.exceptions import AccessDenied, ValidationFailure
from apps.core.sequences import next_number

from .models import FeeRecord, Payment, PaymentMode


def create_fee_record(allocation):
    record, _ = FeeRecord.objects.get_or_create(
        allocation=allocation,
        defaults={
            "total_amount": allocation.room.annual_fee,
            "academic_year": allocation.academic_year,
        },
    )
    return record


def move_fee_record(old_allocation, new_allocation, new_total):
    record = FeeRecord.objects.select_for_update().get(allocation=old_allocation)
    placeholder = (
        FeeRecord.objects.select_for_update()
        .filter(allocation=new_allocation)
        .first()
    )
    if placeholder:
        placeholder.delete()
    record.allocation = new_allocation
    record.total_amount = new_total
    record.save(update_fields=["allocation", "total_amount", "updated_at"])
    return record


def _staff_can_manage_allocation(actor, allocation):
    if not actor.is_authenticated or actor.role not in (Role.WARDEN, Role.ADMIN):
        raise AccessDenied()

    if actor.role == Role.ADMIN:
        return True

    if not actor.hostels.filter(
        pk=allocation.room.hostel_id, is_active=True
    ).exists():
        raise AccessDenied()
    return True


@transaction.atomic
def record_payment(
    *,
    allocation_id,
    actor,
    amount,
    mode,
    txn_reference,
    paid_on,
    submission_id,
    request=None,
):
    """Record one fee payment and confirm a fully-paid provisional allocation.

    The fee record is locked for the complete operation.  A client retry with
    the same submission_id therefore returns the already-created payment
    instead of creating a second payment.
    """
    allocation = (
        Allocation.objects.select_for_update()
        .select_related("room__hostel")
        .filter(pk=allocation_id)
        .first()
    )
    if allocation is None:
        raise ValidationFailure("Allocation not found.")

    _staff_can_manage_allocation(actor, allocation)

    fee_record = (
        FeeRecord.objects.select_for_update()
        .select_related("allocation")
        .filter(allocation=allocation)
        .first()
    )
    if fee_record is None:
        raise ValidationFailure("No fee record exists for this allocation.")

    if submission_id:
        existing = (
            Payment.objects.select_for_update()
            .filter(submission_id=submission_id)
            .first()
        )
        if existing:
            return existing

    amount = Decimal(amount)
    if amount <= Decimal("0.00"):
        raise ValidationFailure("Amount must be greater than zero.")

    balance = fee_record.balance
    if amount > balance:
        raise ValidationFailure(
            f"Amount exceeds the outstanding balance of INR {balance:.2f}"
        )

    if mode not in PaymentMode.values:
        raise ValidationFailure("Select a valid payment mode.")

    txn_reference = (txn_reference or "").strip()
    if mode != PaymentMode.CASH and not txn_reference:
        raise ValidationFailure(
            "Transaction reference is required for non-cash payments."
        )
    if paid_on > timezone.localdate():
        raise ValidationFailure("Payment date cannot be in the future.")

    old_balance = balance
    payment = Payment.objects.create(
        fee_record=fee_record,
        receipt_no=next_number("RCP"),
        amount=amount,
        mode=mode,
        txn_reference=txn_reference,
        paid_on=paid_on,
        recorded_by=actor,
        submission_id=submission_id or None,
    )

    new_balance = fee_record.balance
    log_action(
        "PAYMENT_RECORDED",
        user=actor,
        entity="payment",
        entity_id=payment.pk,
        old=f"balance={old_balance:.2f}",
        new=f"balance={new_balance:.2f}; receipt={payment.receipt_no}",
        request=request,
    )

    if new_balance <= Decimal("0.00") and allocation.status == AllocationStatus.PROVISIONAL:
        confirm_allocation(allocation)

    return payment
