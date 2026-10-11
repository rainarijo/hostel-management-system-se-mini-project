from django.shortcuts import render

from apps.accounts.models import Role
from apps.core.permissions import role_required


@role_required(Role.STUDENT, Role.WARDEN, Role.ADMIN)
def index(request):
    """Announcements (FR-9.1 - FR-9.3).

    Planned for Sprint 4: replace this placeholder.
    """
    context = {"feature": "Announcements", "frs": "FR-9.1 - FR-9.3", "sprint": 4}
    return render(request, "coming_soon.html", context)
