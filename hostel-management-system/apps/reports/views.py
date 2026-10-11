from django.shortcuts import render

from apps.accounts.models import Role
from apps.core.permissions import role_required


@role_required(Role.WARDEN, Role.ADMIN)
def index(request):
    """Reports (FR-8.1 - FR-8.4).

    Planned for Sprint 4: replace this placeholder.
    """
    context = {"feature": "Reports", "frs": "FR-8.1 - FR-8.4", "sprint": 4}
    return render(request, "coming_soon.html", context)
