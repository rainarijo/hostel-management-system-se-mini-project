"""Gap-free document numbers: APP-2026-00001, CMP-2026-00001, RCP-2026-00001 (SAD 4.1.2)."""
from django.db import transaction
from django.utils import timezone

from .models import DocumentSequence


def next_number(prefix, year=None):
    """Return the next number for a prefix, e.g. next_number("APP") -> "APP-2026-00001".

    Call this inside the same transaction that saves the record, so a failed
    save does not leave a gap.
    """
    year = year or timezone.now().year
    with transaction.atomic():
        seq, _ = DocumentSequence.objects.select_for_update().get_or_create(
            prefix=prefix, year=year, defaults={"last_no": 0})
        seq.last_no += 1
        seq.save(update_fields=["last_no"])
        return f"{prefix}-{year}-{seq.last_no:05d}"
