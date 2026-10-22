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
