"""Student profile services for Issue #33 secure file delivery and PDF export."""

from pathlib import Path

from django.conf import settings
from django.core.exceptions import SuspiciousFileOperation
from django.db import transaction

from apps.accounts.models import Role
from apps.allocation.models import Allocation
from apps.core.exceptions import ObjectNotFound
from apps.students.models import StudentProfile


PROFILE_PDF_FIELDS = (
    ("SRN", "srn"),
    ("Name", "name"),
    ("Gender", "get_gender_display"),
    ("Programme", "program"),
    ("Year", "year"),
    ("Mobile", "mobile"),
    ("Personal email", "personal_email"),
    ("Permanent address", "permanent_address"),
    ("Guardian name", "guardian_name"),
    ("Guardian relationship", "guardian_relationship"),
    ("Guardian mobile", "guardian_mobile"),
    ("Emergency contact name", "emergency_contact_name"),
    ("Emergency contact mobile", "emergency_contact_mobile"),
    ("Blood group", "blood_group"),
)


def get_authorized_profile(actor, profile_id):
    """Return a profile only when the actor is authorized to access it.

    Deliberately returns ObjectNotFound for both missing and out-of-scope
    objects so the HTTP layer can expose a uniform 404 and avoid IDOR leaks.
    """
    profile = StudentProfile.objects.filter(pk=profile_id).first()
    if profile is None:
        raise ObjectNotFound("Student profile not found.")

    if actor.role == Role.ADMIN:
        return profile

    if actor.role == Role.STUDENT and profile.user_id == actor.pk:
        return profile

    raise ObjectNotFound("Student profile not found.")


def secure_photo_path(profile):
    """Return a validated filesystem path for a stored profile photo."""
    if not profile.photo:
        raise ObjectNotFound("Profile photograph not found.")

    media_root = Path(settings.MEDIA_ROOT).resolve()
    try:
        photo_path = Path(profile.photo.path).resolve()
        photo_path.relative_to(media_root)
    except (FileNotFoundError, ValueError, SuspiciousFileOperation) as exc:
        raise ObjectNotFound("Profile photograph not found.") from exc

    if not photo_path.is_file():
        raise ObjectNotFound("Profile photograph not found.")

    return photo_path


def profile_pdf_data(profile):
    """Build only SRS Appendix-B profile fields plus allocation data."""
    values = []
    for label, field_name in PROFILE_PDF_FIELDS:
        value = getattr(profile, field_name)
        if callable(value):
            value = value()
        values.append((label, value or "—"))

    allocations = (
        Allocation.objects.filter(student=profile)
        .select_related("room__hostel")
        .order_by("-start_date", "-pk")
    )
    allocation_rows = []
    for allocation in allocations:
        allocation_rows.append(
            (
                getattr(allocation.room.hostel, "name", "—"),
                getattr(allocation.room, "room_no", "—"),
                getattr(allocation, "bed_no", "—"),
                getattr(allocation, "academic_year", "—"),
                getattr(allocation, "start_date", "—"),
                getattr(allocation, "end_date", None) or "—",
                allocation.get_status_display(),
            )
        )

    return values, allocation_rows


def _pdf_escape(value):
    text = str(value if value not in (None, "") else "—")
    text = text.encode("latin-1", "replace").decode("latin-1")
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def build_profile_pdf(profile):
    """Create a dependency-free PDF containing profile and allocation data."""
    profile_values, allocation_rows = profile_pdf_data(profile)
    lines = ["Student Profile", ""]
    for label, value in profile_values:
        lines.append(f"{label}: {value}")

    lines.extend(["", "Room Allocation"])
    if allocation_rows:
        for index, row in enumerate(allocation_rows, start=1):
            lines.append(f"Allocation {index}")
            labels = (
                "Hostel", "Room", "Bed", "Academic year",
                "Start date", "End date", "Status",
            )
            for label, value in zip(labels, row):
                lines.append(f"{label}: {value}")
            lines.append("")
    else:
        lines.append("No allocation records.")

    # Match the existing project's dependency-free PDF strategy.
    page_chunks = [lines[index:index + 42] for index in range(0, len(lines), 42)] or [[]]
    objects = [
        b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n",
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    page_refs = []
    for chunk in page_chunks:
        page_id = len(objects)
        content_id = page_id + 1
        page_refs.append(f"{page_id} 0 R")
        commands = ["BT", "/F1 9 Tf", "40 555 Td", "12 TL"]
        for line in chunk:
            commands.append(f"({_pdf_escape(line)}) Tj")
            commands.append("T*")
        commands.append("ET")
        content = "\n".join(commands).encode("latin-1")
        objects.append(
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 842 595] "
            f"/Resources << /Font << /F1 3 0 R >> >> "
            f"/Contents {content_id} 0 R >>".encode("ascii")
        )
        objects.append(
            b"<< /Length %d >>\nstream\n%s\nendstream" %
            (len(content), content)
        )

    objects[2] = (
        f"<< /Type /Pages /Kids [{' '.join(page_refs)}] "
        f"/Count {len(page_refs)} >>".encode("ascii")
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
        f"trailer\n<< /Size {len(objects)} /Root 1 0 R >>\n"
        f"startxref\n{xref_offset}\n%%EOF\n".encode("ascii")
    )
    return bytes(output)


@transaction.atomic
def update_profile(actor, profile, form):
    """Save a validated profile form within a transaction."""
    if actor.role != Role.ADMIN and profile.user_id != actor.pk:
        raise ObjectNotFound("Student profile not found.")
    return form.save()
