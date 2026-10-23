from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import Role, User
from apps.rooms.models import Hostel, Room

CSV_HEADER = "hostel_name,room_no,floor,room_type,capacity,annual_fee,status\n"


class RoomCSVImportTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user("admin@hms.local", "Strongpass2026", role=Role.ADMIN)
        self.warden = User.objects.create_user("warden@hms.local", "Strongpass2026", role=Role.WARDEN)
        self.hostel = Hostel.objects.create(name="North Hall", gender_type="M")
        self.url = reverse("room_import")

    def upload(self, content, filename="rooms.csv"):
        return self.client.post(self.url, {
            "file": SimpleUploadedFile(filename, content.encode("utf-8"), content_type="text/csv"),
        })

    def test_import_saves_valid_rows_and_reports_invalid_and_duplicate_rows(self):
        self.client.force_login(self.admin)
        content = (
            CSV_HEADER
            + "North Hall,101,1,DOUBLE,2,75000.00,AVAILABLE\n"
            + "North Hall,102,1,DOUBLE,5,75000.00,AVAILABLE\n"
            + "North Hall,101,1,SINGLE,1,50000.00,FULL\n"
        )
        response = self.upload(content)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Room.objects.count(), 1)
        self.assertEqual(Room.objects.get().room_no, "101")
        self.assertEqual([row["row"] for row in response.context["report"]["accepted"]], [2])
        rejected = response.context["report"]["rejected"]
        self.assertEqual([row["row"] for row in rejected], [3, 4])
        self.assertIn("capacity", rejected[0]["reason"].lower())
        self.assertTrue(rejected[1]["reason"])

    def test_unknown_hostel_and_invalid_room_choices_are_reported_by_row(self):
        self.client.force_login(self.admin)
        content = (
            CSV_HEADER
            + "Unknown Hall,101,1,DOUBLE,2,75000.00,AVAILABLE\n"
            + "North Hall,102,1,QUADRUPLE,2,75000.00,AVAILABLE\n"
        )
        response = self.upload(content)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Room.objects.count(), 0)
        rejected = response.context["report"]["rejected"]
        self.assertEqual([row["row"] for row in rejected], [2, 3])
        self.assertIn("Hostel not found", rejected[0]["reason"])
        self.assertTrue(rejected[1]["reason"])

    def test_header_must_match_approved_csv_schema(self):
        self.client.force_login(self.admin)
        response = self.upload("room_no,hostel_name\n101,North Hall\n")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["form"].errors["file"])
        self.assertEqual(Room.objects.count(), 0)

    def test_only_administrator_can_import_rooms(self):
        self.client.force_login(self.warden)
        response = self.upload(CSV_HEADER + "North Hall,101,1,DOUBLE,2,75000.00,AVAILABLE\n")
        self.assertEqual(response.status_code, 403)
        self.assertEqual(Room.objects.count(), 0)
