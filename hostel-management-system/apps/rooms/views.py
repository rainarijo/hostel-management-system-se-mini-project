from django.shortcuts import render

from apps.accounts.models import Role
from apps.core.permissions import role_required


@role_required(Role.WARDEN, Role.ADMIN)
def index(request):
    """Hostel and room management (FR-3.1 - FR-3.7).

    Planned for Sprint 1: replace this placeholder.
    """
    context = {"feature": "Hostel and room management", "frs": "FR-3.1 - FR-3.7", "sprint": 1}
    return render(request, "coming_soon.html", context)
