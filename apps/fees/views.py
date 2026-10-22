from django.shortcuts import get_object_or_404, redirect, render

from apps.accounts.models import Role
from apps.allocation.models import Allocation
from apps.core.permissions import role_required
from apps.students.models import StudentProfile


@role_required(Role.STUDENT, Role.WARDEN, Role.ADMIN)
def index(request):
    """Fees. Students go to their dues page; staff screens (FR-7.2 - FR-7.6) come in Sprint 2."""
    if request.user.role == Role.STUDENT:
        return redirect("fees:my_dues")
    context = {"feature": "Fees and payments", "frs": "FR-7.2 - FR-7.6", "sprint": 2}
    return render(request, "coming_soon.html", context)


@role_required(Role.STUDENT)
def my_dues(request):
    """FR-7.5: total fee, amount paid, balance and payment history for each of the student's allocations."""
    student = get_object_or_404(StudentProfile, user=request.user)
    allocations = (Allocation.objects.filter(student=student)
                   .select_related("room__hostel", "fee_record")
                   .prefetch_related("fee_record__payments")
                   .order_by("-start_date", "-pk"))
    return render(request, "fees/my_dues.html", {"allocations": allocations})
