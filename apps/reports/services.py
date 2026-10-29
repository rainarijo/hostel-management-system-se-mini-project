"""Report queries and exports (FR-8.2 - FR-8.4)."""
import csv
import io
import textwrap
from datetime import date, datetime
from decimal import Decimal

from django.db.models import Count, DecimalField, F, Q, Sum, Value
from django.db.models.functions import Coalesce
from django.utils import timezone

from apps.accounts.models import Role
from apps.allocation.models import ACTIVE_STATUSES, Allocation, AllocationStatus
from apps.allocation.services import scoped_hostels
from apps.complaints.models import Complaint
from apps.core.exceptions import AccessDenied
from apps.fees.models import FeeRecord
from apps.rooms.models import Room

REPORTS = {
    "occupancy": {
        "title": "Occupancy Report",
        "description": "Room capacity, occupied beds, vacancies, and room status.",
        "headers": ["Hostel", "Floor", "Room Number", "Room Type", "Capacity", "Occupied Beds",
                    "Vacant Beds", "Status", "Occupancy %"],
    },
    "residents": {
        "title": "Resident List",
        "description": "Students with active room allocations and contact details.",
        "headers": ["SRN", "Student Name", "Hostel", "Room", "Bed", "Year of Study", "Mobile Number",
                    "Guardian Mobile", "Blood Group", "Allocation Status", "Allocation Start Date"],
    },
    "fee-dues": {
        "title": "Fee Dues Report",
        "description": "Outstanding allocation fees and amounts paid.",
        "headers": ["SRN", "Student Name", "Hostel", "Room", "Annual Fee", "Amount Paid", "Balance",
                    "Days Since Allocation"],
    },
    "complaints": {
        "title": "Complaint Summary",
        "description": "Complaints raised for rooms in the authorized hostel scope.",
        "headers": ["Complaint ID", "Hostel", "Room", "Category", "Raised On", "Status", "Days Open",
                    "Resolved On", "Warden Remark"],
    },
}


def report_hostels(actor):
    """Hostels an actor is authorized to report on."""
    if actor.role not in (Role.WARDEN, Role.ADMIN):
        raise AccessDenied()
    return scoped_hostels(actor).order_by("name")


def _hostel_scope(actor, selected_hostel):
    hostels = report_hostels(actor)
    if selected_hostel is not None:
        if not hostels.filter(pk=selected_hostel.pk).exists():
            raise AccessDenied("You cannot access reports for this hostel.")
        hostels = hostels.filter(pk=selected_hostel.pk)
    return hostels


def _allocation_date_filter(queryset, field, date_from, date_to):
    if date_from:
        queryset = queryset.filter(**{f"{field}__gte": date_from})
    if date_to:
        queryset = queryset.filter(**{f"{field}__lte": date_to})
    return queryset


def _occupancy_rows(hostels, date_from, date_to, today):
    rooms = Room.objects.filter(hostel__in=hostels, is_active=True).select_related("hostel")
    if date_from or date_to:
        period_start = date_from or date_to
        period_end = date_to or date_from
        occupancy_filter = Q(
            allocations__status__in=[
                AllocationStatus.PROVISIONAL, AllocationStatus.CONFIRMED, AllocationStatus.ENDED,
            ],
            allocations__start_date__lte=period_end,
        ) & (Q(allocations__end_date__isnull=True) | Q(allocations__end_date__gte=period_start))
    else:
        occupancy_filter = Q(
            allocations__status__in=ACTIVE_STATUSES,
            allocations__start_date__lte=today,
        ) & (Q(allocations__end_date__isnull=True) | Q(allocations__end_date__gte=today))

    rooms = rooms.annotate(
        occupied=Count("allocations__bed_no", filter=occupancy_filter, distinct=True),
    ).order_by("hostel__name", "floor", "room_no")

    rows = []
    for room in rooms:
        percentage = round(room.occupied * 100 / room.capacity, 1) if room.capacity else 0
        rows.append([
            room.hostel.name, room.floor, room.room_no, room.get_room_type_display(), room.capacity,
            room.occupied, max(room.capacity - room.occupied, 0), room.get_status_display(), percentage,
        ])
    return rows


def _resident_rows(hostels, date_from, date_to):
    allocations = (Allocation.objects.active().filter(room__hostel__in=hostels)
                   .select_related("student", "room__hostel"))
    allocations = _allocation_date_filter(allocations, "start_date", date_from, date_to)
    allocations = allocations.order_by("room__hostel__name", "room__floor", "room__room_no", "bed_no")
    return [[
        allocation.student.srn, allocation.student.name, allocation.room.hostel.name, allocation.room.room_no,
        allocation.bed_no, allocation.student.year, allocation.student.mobile, allocation.student.guardian_mobile,
        allocation.student.blood_group, allocation.get_status_display(), allocation.start_date,
    ] for allocation in allocations]


def _fee_rows(hostels, date_from, date_to, today):
    records = (FeeRecord.objects.filter(allocation__room__hostel__in=hostels)
               .select_related("allocation__student", "allocation__room__hostel")
               .annotate(amount_paid_value=Coalesce(
                   Sum("payments__amount"), Value(Decimal("0.00")),
                   output_field=DecimalField(max_digits=9, decimal_places=2),
               )))
    records = _allocation_date_filter(records, "allocation__start_date", date_from, date_to)
    records = records.filter(total_amount__gt=F("amount_paid_value"))
    records = records.order_by("allocation__room__hostel__name", "allocation__student__srn")
    return [[
        record.allocation.student.srn, record.allocation.student.name,
        record.allocation.room.hostel.name, record.allocation.room.room_no,
        record.total_amount, record.amount_paid_value, record.total_amount - record.amount_paid_value,
        (today - record.allocation.start_date).days,
    ] for record in records]


def _complaint_rows(hostels, date_from, date_to, today):
    complaints = (Complaint.objects.filter(room__hostel__in=hostels)
                  .select_related("room__hostel"))
    if date_from:
        complaints = complaints.filter(created_at__date__gte=date_from)
    if date_to:
        complaints = complaints.filter(created_at__date__lte=date_to)
    complaints = complaints.order_by("-created_at", "complaint_no")
    rows = []
    for complaint in complaints:
        raised = timezone.localtime(complaint.created_at).date()
        resolved = timezone.localtime(complaint.resolved_at).date() if complaint.resolved_at else None
        last_day = resolved or today
        rows.append([
            complaint.complaint_no, complaint.room.hostel.name, complaint.room.room_no,
            complaint.get_category_display(), raised, complaint.get_status_display(),
            max((last_day - raised).days, 0), resolved, complaint.remark,
        ])
    return rows


def build_report(actor, report_type, selected_hostel=None, date_from=None, date_to=None, today=None):
    """Build report headers and rows after enforcing the actor's current hostel scope."""
    if report_type not in REPORTS:
        raise LookupError("Unknown report type.")
    hostels = _hostel_scope(actor, selected_hostel)
    today = today or timezone.localdate()
    if report_type == "occupancy":
        rows = _occupancy_rows(hostels, date_from, date_to, today)
    elif report_type == "residents":
        rows = _resident_rows(hostels, date_from, date_to)
    elif report_type == "fee-dues":
        rows = _fee_rows(hostels, date_from, date_to, today)
    else:
        rows = _complaint_rows(hostels, date_from, date_to, today)

    return {
        "key": report_type,
        "title": REPORTS[report_type]["title"],
        "headers": REPORTS[report_type]["headers"],
        "rows": rows,
        "filters": {
            "hostel": selected_hostel.name if selected_hostel else "All authorized hostels",
            "date_from": date_from,
            "date_to": date_to,
        },
    }


def csv_content(report):
    output = io.StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(report["headers"])
    writer.writerows(report["rows"])
    return output.getvalue()


def _display_value(value):
    if value is None or value == "":
        return "—"
    if isinstance(value, datetime):
        return timezone.localtime(value).strftime("%Y-%m-%d %H:%M")
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Decimal):
        return f"{value:.2f}"
    return str(value)


def pdf_content(report):
    """Create a small, dependency-free, paginated text PDF for the report."""
    lines = [
        report["title"],
        f"Generated: {timezone.localtime().strftime('%Y-%m-%d %H:%M')}",
        (f"Hostel: {report['filters']['hostel']} | "
         f"From: {_display_value(report['filters']['date_from'])} | "
         f"To: {_display_value(report['filters']['date_to'])}"),
        "",
    ]
    if report["rows"]:
        for index, row in enumerate(report["rows"], start=1):
            lines.append(f"Record {index}")
            for label, value in zip(report["headers"], row):
                wrapped = textwrap.wrap(f"{label}: {_display_value(value)}", width=98) or [f"{label}: "]
                lines.extend(wrapped)
            lines.append("")
    else:
        lines.append("No records matched the selected filters.")

    page_chunks = [lines[index:index + 42] for index in range(0, len(lines), 42)]
    objects = [
        b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n",
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"",  # Pages object is filled after the page references are known.
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    page_refs = []
    for chunk in page_chunks:
        page_id = len(objects)
        content_id = page_id + 1
        page_refs.append(f"{page_id} 0 R")
        commands = ["BT", "/F1 9 Tf", "40 555 Td", "12 TL"]
        for line in chunk:
            safe_line = line.encode("latin-1", "replace").decode("latin-1")
            escaped = safe_line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
            commands.append(f"({escaped}) Tj")
            commands.append("T*")
        commands.append("ET")
        content = "\n".join(commands).encode("latin-1")
        objects.append(
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 842 595] "
            f"/Resources << /Font << /F1 3 0 R >> >> "
            f"/Contents {content_id} 0 R >>".encode("ascii")
        )
        objects.append(b"<< /Length %d >>\nstream\n%s\nendstream" % (len(content), content))
    objects[2] = (
        f"<< /Type /Pages /Kids [{' '.join(page_refs)}] /Count {len(page_refs)} >>".encode("ascii")
    )
    output = bytearray(objects[0])
    offsets = [0]
    for object_id, body in enumerate(objects[1:], start=1):
        offsets.append(len(output))
        output.extend(f"{object_id} 0 obj\n".encode("ascii"))
        output.extend(body)
        output.extend(b"\nendobj\n")
    xref_offset = len(output)
    output.extend(f"xref\n0 {len(objects)}\n".encode("ascii"))
    output.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        output.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
    output.extend(
        f"trailer\n<< /Size {len(objects)} /Root 1 0 R >>\nstartxref\n{xref_offset}\n%%EOF\n".encode("ascii")
    )
    return bytes(output)
