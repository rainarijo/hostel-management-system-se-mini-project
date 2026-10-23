import csv
import io

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from .models import Hostel, Room

ROOM_CSV_FIELDS = ("hostel_name", "room_no", "floor", "room_type", "capacity", "annual_fee", "status")


class CSVImportError(Exception):
    pass


def _validation_reason(error):
    reasons = []
    for field, messages in error.message_dict.items():
        label = field if field == "__all__" else Room._meta.get_field(field).verbose_name
        reasons.extend(f"{label}: {message}" for message in messages)
    return "; ".join(reasons)


def import_rooms(uploaded_file):
    try:
        content = uploaded_file.read().decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise CSVImportError("The CSV file must use UTF-8 encoding.") from exc

    reader = csv.DictReader(io.StringIO(content, newline=""), strict=True)
    try:
        fieldnames = reader.fieldnames
    except csv.Error as exc:
        raise CSVImportError(f"Invalid CSV header: {exc}") from exc
    if tuple(fieldnames or ()) != ROOM_CSV_FIELDS:
        expected = ", ".join(ROOM_CSV_FIELDS)
        raise CSVImportError(f"CSV header must be exactly: {expected}.")

    accepted = []
    rejected = []

    def reject(row_number, reason, values=None):
        rejected.append({"row": row_number, "values": values or {}, "reason": reason})

    try:
        for row_number, row in enumerate(reader, start=2):
            if None in row or any(value is None for value in row.values()):
                reject(row_number, "The row has missing or extra columns.", row)
                continue

            values = {key: value.strip() for key, value in row.items()}
            hostel = Hostel.objects.filter(name=values["hostel_name"]).first()
            if hostel is None:
                reject(row_number, "Hostel not found.", values)
                continue

            room = Room(
                hostel=hostel,
                room_no=values["room_no"],
                floor=values["floor"],
                room_type=values["room_type"].upper(),
                capacity=values["capacity"],
                annual_fee=values["annual_fee"],
                status=values["status"].upper(),
            )
            try:
                room.full_clean()
                with transaction.atomic():
                    room.save(force_insert=True)
            except ValidationError as exc:
                reject(row_number, _validation_reason(exc), values)
                continue
            except IntegrityError:
                reject(row_number, "The room conflicts with an existing room or database constraint.", values)
                continue

            accepted.append({"row": row_number, "values": values, "room": room})
    except csv.Error as exc:
        reject(reader.line_num, f"Invalid CSV row: {exc}")

    return {"accepted": accepted, "rejected": rejected}
