"""Signals sent by the allocation service (SAD 3.3). Receivers live in the apps that react to them."""
import django.dispatch

# Sent inside the allocate() transaction with allocation=<Allocation>. A receiver that raises rolls the allocation back.
allocation_created = django.dispatch.Signal()
