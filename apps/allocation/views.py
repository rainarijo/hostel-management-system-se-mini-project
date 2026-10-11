from django.shortcuts import render

from apps.accounts.models import Role
from apps.core.permissions import role_required


@role_required(Role.STUDENT, Role.WARDEN, Role.ADMIN)
def index(request):
    """Room applications and allocation (FR-4.1 - FR-4.10, FR-5.1 - FR-5.5).

    Planned for Sprint 2: replace this placeholder.
    """
    context = {"feature": "Room applications and allocation", "frs": "FR-4.1 - FR-4.10, FR-5.1 - FR-5.5", "sprint": 2}
    return render(request, "coming_soon.html", context)
