from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render

from apps.accounts.models import Role
from apps.allocation.models import Allocation
from apps.core.permissions import role_required
from apps.students.models import StudentProfile

from .forms import ComplaintForm
from .models import Complaint
from .services import NoActiveAllocation, raise_complaint


@role_required(Role.STUDENT, Role.WARDEN, Role.ADMIN)
def index(request):
    """Complaints. Students raise and list their own complaints (FR-6.1, FR-6.2).

    Warden handling (FR-6.3 - FR-6.5) is planned for Sprint 2: placeholder page for now.
    """
    if request.user.role != Role.STUDENT:
        context = {"feature": "Complaints", "frs": "FR-6.3 - FR-6.5", "sprint": 2}
        return render(request, "coming_soon.html", context)

    student = get_object_or_404(StudentProfile, user=request.user)
    status = 200
    if request.method == "POST":
        form = ComplaintForm(request.POST)
        if form.is_valid():
            try:
                complaint = raise_complaint(request.user, student, request=request, **form.cleaned_data)
            except NoActiveAllocation as exc:
                messages.error(request, str(exc))
                status = 409          # business-rule rejection (SAD 4.3.1)
            else:
                messages.success(request, f"Complaint {complaint.complaint_no} raised.")
                return redirect("complaints:index")      # post-redirect-get (SAD 4.4.2)
    else:
        form = ComplaintForm()

    context = {
        "form": form,
        "complaints": Complaint.objects.filter(student=student).select_related("room__hostel"),
        "has_allocation": Allocation.objects.active().filter(student=student).exists(),
    }
    return render(request, "complaints/index.html", context, status=status)
