from django.http import Http404, HttpResponse
from django.shortcuts import render
from django.urls import reverse
from django.utils.http import urlencode

from apps.accounts.models import Role
from apps.core.permissions import role_required

from .forms import ReportFilterForm
from .services import REPORTS, build_report, csv_content, pdf_content, report_hostels


def _report_context(request, report_type):
    form = ReportFilterForm(request.GET, hostels=report_hostels(request.user))
    report = None
    if form.is_valid():
        report = build_report(
            request.user, report_type,
            selected_hostel=form.cleaned_data["hostel"],
            date_from=form.cleaned_data["date_from"],
            date_to=form.cleaned_data["date_to"],
        )
    query = {}
    if form.is_valid():
        selected_hostel = form.cleaned_data["hostel"]
        if selected_hostel:
            query["hostel"] = selected_hostel.pk
        if form.cleaned_data["date_from"]:
            query["date_from"] = form.cleaned_data["date_from"].isoformat()
        if form.cleaned_data["date_to"]:
            query["date_to"] = form.cleaned_data["date_to"].isoformat()
    query_string = urlencode(query)
    if report:
        report["records"] = [
            list(zip(report["headers"], row)) for row in report["rows"]
        ]
    return {
        "report": report,
        "report_title": REPORTS[report_type]["title"],
        "form": form,
        "export_query": query_string,
        "csv_url": reverse("reports:export", args=[report_type, "csv"]),
        "pdf_url": reverse("reports:export", args=[report_type, "pdf"]),
        "date_filter_note": {
            "occupancy": "For a date range, a bed is counted if allocated at any time during that period.",
            "residents": "Date filters use allocation start date.",
            "fee-dues": "Date filters use allocation start date.",
            "complaints": "Date filters use the date the complaint was raised.",
        }[report_type],
    }


@role_required(Role.WARDEN, Role.ADMIN)
def index(request):
    return render(request, "reports/index.html", {"reports": REPORTS.items()})


@role_required(Role.WARDEN, Role.ADMIN)
def report_detail(request, report_type):
    _ensure_report_type(report_type)
    context = _report_context(request, report_type)
    return render(
        request, "reports/report.html", context,
        status=400 if not context["form"].is_valid() else 200,
    )


@role_required(Role.WARDEN, Role.ADMIN)
def export(request, report_type, export_format):
    _ensure_report_type(report_type)
    if export_format not in {"csv", "pdf"}:
        return HttpResponse("Unsupported export format.", status=404)
    context = _report_context(request, report_type)
    if not context["form"].is_valid():
        return render(request, "reports/report.html", context, status=400)
    report = context["report"]
    filename = f"{report_type}-report"
    if export_format == "csv":
        response = HttpResponse(csv_content(report), content_type="text/csv; charset=utf-8")
        filename += ".csv"
    else:
        response = HttpResponse(pdf_content(report), content_type="application/pdf")
        filename += ".pdf"
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


def _ensure_report_type(report_type):
    if report_type not in REPORTS:
        raise Http404("Report not found.")
