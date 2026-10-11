from django.shortcuts import render

from apps.accounts.models import Role
from apps.core.permissions import role_required


@role_required(Role.STUDENT, Role.WARDEN, Role.ADMIN)
def index(request):
    """Fees and payments (FR-7.1 - FR-7.6).

    Planned for Sprint 3: replace this placeholder.
    """
    context = {"feature": "Fees and payments", "frs": "FR-7.1 - FR-7.6", "sprint": 3}
    return render(request, "coming_soon.html", context)
