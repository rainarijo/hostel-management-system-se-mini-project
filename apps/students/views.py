from django.shortcuts import render

from apps.accounts.models import Role
from apps.core.permissions import role_required


@role_required(Role.STUDENT, Role.WARDEN, Role.ADMIN)
def index(request):
    """Student profiles and search (FR-2.1 - FR-2.7).

    Planned for Sprint 1: replace this placeholder.
    """
    context = {"feature": "Student profiles and search", "frs": "FR-2.1 - FR-2.7", "sprint": 1}
    return render(request, "coming_soon.html", context)
