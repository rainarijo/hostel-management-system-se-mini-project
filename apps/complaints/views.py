from django.contrib import messages
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render

from apps.accounts.models import Role
from apps.allocation.models import Allocation
from apps.core.permissions import role_required
from apps.students.models import StudentProfile

from .forms import ComplaintForm, ComplaintReopenForm, ComplaintStatusForm
from .models import Complaint
from .services import (
    InvalidComplaintTransition,
    NoActiveAllocation,
    ReopenWindowExpired,
    change_status,
    overdue_complaints,
    raise_complaint,
    reopen_complaint,
)


def _warden_scope(complaints, user):
    """Restrict Warden queries to their assigned hostels."""
    if user.role == Role.ADMIN:
        return complaints

    return complaints.filter(room__hostel__wardens=user)


@role_required(Role.STUDENT, Role.WARDEN, Role.ADMIN)
def index(request):
    if request.user.role == Role.STUDENT:
        student = get_object_or_404(StudentProfile, user=request.user)
        status = 200
        if request.method == "POST":
            form = ComplaintForm(request.POST)
            if form.is_valid():
                try:
                    complaint = raise_complaint(
                        request.user,
                        student,
                        request=request,
                        **form.cleaned_data,
                    )
                except NoActiveAllocation as exc:
                    messages.error(request, str(exc))
                    status = 409
                else:
                    messages.success(
                        request,
                        f"Complaint {complaint.complaint_no} raised.",
                    )
                    return redirect("complaints:index")
        else:
            form = ComplaintForm()

        context = {
            "form": form,
            "complaints": Complaint.objects.filter(
                student=student
            ).select_related("room__hostel"),
            "has_allocation": Allocation.objects.active()
            .filter(student=student)
            .exists(),
        }
        return render(request, "complaints/index.html", context, status=status)

    complaints = _warden_scope(
        Complaint.objects.select_related("student", "room__hostel"),
        request.user,
    )
    context = {
        "complaints": complaints,
        "overdue_complaints": overdue_complaints(complaints),
    }
    return render(request, "complaints/warden_index.html", context)


@role_required(Role.WARDEN, Role.ADMIN)
def change_complaint_status(request, complaint_no):
    complaints = _warden_scope(Complaint.objects.all(), request.user)
    complaint = get_object_or_404(complaints, complaint_no=complaint_no)

    if request.method != "POST":
        raise Http404

    form = ComplaintStatusForm(
        request.POST,
        current_status=complaint.status,
    )
    if form.is_valid():
        try:
            change_status(
                complaint,
                form.cleaned_data["status"],
                form.cleaned_data["remark"],
                request.user,
                request=request,
            )
        except InvalidComplaintTransition as exc:
            form.add_error(None, str(exc))
        else:
            messages.success(
                request,
                f"Complaint {complaint.complaint_no} updated.",
            )
            return redirect("complaints:index")

    return render(
        request,
        "complaints/status_form.html",
        {"complaint": complaint, "form": form},
        status=400,
    )


@role_required(Role.STUDENT)
def reopen(request, complaint_no):
    student = get_object_or_404(StudentProfile, user=request.user)
    complaint = get_object_or_404(
        Complaint,
        complaint_no=complaint_no,
        student=student,
    )

    if request.method != "POST":
        raise Http404

    form = ComplaintReopenForm(request.POST)
    if form.is_valid():
        try:
            reopen_complaint(complaint, request.user, request=request)
        except (InvalidComplaintTransition, ReopenWindowExpired) as exc:
            form.add_error(None, str(exc))
        else:
            messages.success(
                request,
                f"Complaint {complaint.complaint_no} reopened.",
            )
            return redirect("complaints:index")

    return render(
        request,
        "complaints/reopen_form.html",
        {"complaint": complaint, "form": form},
        status=400,
    )
