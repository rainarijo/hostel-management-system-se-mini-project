from django.shortcuts import render

from apps.accounts.models import Role
from apps.core.permissions import role_required


@role_required(Role.STUDENT, Role.WARDEN, Role.ADMIN)
def index(request):
    """Complaints (FR-6.1 - FR-6.5).

    Planned for Sprint 3: replace this placeholder.
    """
    context = {"feature": "Complaints", "frs": "FR-6.1 - FR-6.5", "sprint": 3}
    return render(request, "coming_soon.html", context)
