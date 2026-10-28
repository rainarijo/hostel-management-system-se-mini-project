"""Fee rules (SAD 4.1.1: rules live in services, not in views)."""
from .models import FeeRecord


def create_fee_record(allocation):
    """FR-7.1: one fee record per allocation, equal to the allocated room's annual fee.

    Safe to call more than once: an allocation never gets a second fee record.
    """
    record, _ = FeeRecord.objects.get_or_create(
        allocation=allocation,
        defaults={"total_amount": allocation.room.annual_fee, "academic_year": allocation.academic_year},
    )
    return record


def move_fee_record(old_allocation, new_allocation, new_total):
    """DD-3: retain the existing fee record and payments when an allocation changes rooms."""
    record = FeeRecord.objects.select_for_update().get(allocation=old_allocation)
    placeholder = FeeRecord.objects.select_for_update().filter(allocation=new_allocation).first()
    if placeholder:
        placeholder.delete()

    record.allocation = new_allocation
    record.total_amount = new_total
    record.save(update_fields=["allocation", "total_amount", "updated_at"])
    return record
