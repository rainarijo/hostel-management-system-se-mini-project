"""C6 reacts to a new allocation without C4 knowing anything about fees (SAD 3.3, arrow 5)."""
from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.allocation.models import Allocation

from .services import create_fee_record


@receiver(post_save, sender=Allocation, dispatch_uid="fees_create_fee_record_for_new_allocation")
def fee_record_for_new_allocation(sender, instance, created, **kwargs):
    if created:
        create_fee_record(instance)
