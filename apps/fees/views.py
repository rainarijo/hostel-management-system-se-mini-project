import uuid
from datetime import timedelta

from django.contrib import messages
from django.core.paginator import Paginator
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from apps.accounts.models import Role
from apps.allocation.models import Allocation, AllocationStatus
from apps.core.permissions import role_required
from apps.students.models import StudentProfile

from .forms import PaymentForm
from .models import FeeRecord, Payment
from .receipts import receipt_pdf
from .services import record_payment


@role_required(Role.STUDENT, Role.WARDEN, Role.ADMIN)
def index(request):
    if request.user.role == Role.STUDENT:
        return redirect("fees:my_dues")

    allocations = (
        Allocation.objects.filter(
            status__in=[
                AllocationStatus.PROVISIONAL,
                AllocationStatus.CONFIRMED,
            ]
        )
        .select_related("student", "room__hostel", "fee_record")
        .order_by("-start_date", "-pk")
    )
    if request.user.role == Role.WARDEN:
        allocations = allocations.filter(
            room__hostel__in=request.user.hostels.filter(is_active=True)
        )

    paginator = Paginator(allocations, 25)
    page = paginator.get_page(request.GET.get("page"))
    return render(request, "fees/index.html", {"page": page})


@role_required(Role.STUDENT)
def my_dues(request):
    student = get_object_or_404(StudentProfile, user=request.user)
    allocations = (
        Allocation.objects.filter(student=student)
        .select_related("room__hostel", "fee_record")
        .prefetch_related("fee_record__payments")
        .order_by("-start_date", "-pk")
    )
    return render(request, "fees/my_dues.html", {"allocations": allocations})


@role_required(Role.WARDEN, Role.ADMIN)
def payment(request, allocation_id):
    allocation = get_object_or_404(
        Allocation.objects.select_related("student", "room__hostel", "fee_record"),
        pk=allocation_id,
    )

    if request.user.role == Role.WARDEN and not request.user.hostels.filter(
        pk=allocation.room.hostel_id, is_active=True
    ).exists():
        return HttpResponse("Forbidden", status=403)

    fee = get_object_or_404(FeeRecord, allocation=allocation)

    if request.method == "POST":
        form = PaymentForm(request.POST)
        if form.is_valid():
            try:
                recorded = record_payment(
                    allocation_id=allocation.pk,
                    actor=request.user,
                    amount=form.cleaned_data["amount"],
                    mode=form.cleaned_data["mode"],
                    txn_reference=form.cleaned_data["txn_reference"],
                    paid_on=form.cleaned_data["paid_on"],
                    submission_id=form.cleaned_data["submission_id"],
                    request=request,
                )
            except Exception as exc:
                from apps.core.exceptions import HMSError

                if isinstance(exc, HMSError):
                    form.add_error(None, exc.message)
                else:
                    raise
            else:
                messages.success(request, "Payment recorded successfully.")
                return redirect(
                    "fees:receipt",
                    receipt_no=recorded.receipt_no,
                )
    else:
        form = PaymentForm(
            initial={
                "paid_on": timezone.localdate(),
                "submission_id": uuid.uuid4(),
            }
        )

    return render(
        request,
        "fees/payment_form.html",
        {"allocation": allocation, "fee": fee, "form": form},
    )


@role_required(Role.STUDENT, Role.WARDEN, Role.ADMIN)
def receipt(request, receipt_no):
    payment_obj = get_object_or_404(
        Payment.objects.select_related(
            "fee_record__allocation__student",
            "fee_record__allocation__room__hostel",
        ),
        receipt_no=receipt_no,
    )
    allocation = payment_obj.fee_record.allocation

    if request.user.role == Role.STUDENT:
        student = get_object_or_404(StudentProfile, user=request.user)
        if allocation.student_id != student.pk:
            return HttpResponse("Forbidden", status=403)
    elif request.user.role == Role.WARDEN:
        if not request.user.hostels.filter(
            pk=allocation.room.hostel_id, is_active=True
        ).exists():
            return HttpResponse("Forbidden", status=403)

    response = HttpResponse(receipt_pdf(payment_obj), content_type="application/pdf")
    response["Content-Disposition"] = (
        f'attachment; filename="{payment_obj.receipt_no}.pdf"'
    )
    return response


@role_required(Role.WARDEN, Role.ADMIN)
def provisional_unpaid(request):
    cutoff = timezone.now() - timedelta(days=15)
    allocations = (
        Allocation.objects.filter(
            status=AllocationStatus.PROVISIONAL,
            created_at__lte=cutoff,
            fee_record__payments__isnull=True,
        )
        .select_related("student", "room__hostel", "fee_record")
        .distinct()
        .order_by("created_at", "pk")
    )

    if request.user.role == Role.WARDEN:
        allocations = allocations.filter(
            room__hostel__in=request.user.hostels.filter(is_active=True)
        )

    paginator = Paginator(allocations, 25)
    page = paginator.get_page(request.GET.get("page"))
    return render(request, "fees/provisional_unpaid.html", {"page": page})
