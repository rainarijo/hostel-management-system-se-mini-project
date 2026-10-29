from datetime import date, timedelta
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import Role, User
from apps.allocation.models import Allocation, AllocationStatus
from apps.complaints.models import Complaint, ComplaintCategory
from apps.rooms.models import Hostel, Room, RoomType
from apps.students.models import StudentProfile

PASSWORD = "Strongpass2026"


class ReportTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.warden = User.objects.create_user("reports-warden@hms.local", PASSWORD, role=Role.WARDEN)
        cls.other_warden = User.objects.create_user("reports-other@hms.local", PASSWORD, role=Role.WARDEN)
        cls.admin = User.objects.create_user("reports-admin@hms.local", PASSWORD, role=Role.ADMIN)
        cls.student_user = User.objects.create_user("reports-student@hms.local", PASSWORD, role=Role.STUDENT)
        cls.student = StudentProfile.objects.create(
            user=cls.student_user, srn="PES1UG24CS901", name="Report Student", gender="M",
            program="B.Tech CSE", year=2, mobile="9845000101", guardian_mobile="9886000101",
            blood_group="O+",
        )
        cls.hostel = Hostel.objects.create(name="Reports Block", gender_type="M")
        cls.hostel.wardens.add(cls.warden)
        cls.other_hostel = Hostel.objects.create(name="Other Reports Block", gender_type="M")
        cls.other_hostel.wardens.add(cls.other_warden)
        cls.room = Room.objects.create(
            hostel=cls.hostel, room_no="301", floor=3, room_type=RoomType.DOUBLE,
            capacity=2, annual_fee=Decimal("75000.00"),
        )
        cls.other_room = Room.objects.create(
            hostel=cls.other_hostel, room_no="401", floor=4, room_type=RoomType.SINGLE,
            capacity=1, annual_fee=Decimal("90000.00"),
        )
        cls.allocation = Allocation.objects.create(
            student=cls.student, room=cls.room, bed_no=1, start_date=date.today() - timedelta(days=12),
            status=AllocationStatus.CONFIRMED, academic_year="2026-2027",
        )
        cls.complaint = Complaint.objects.create(
            student=cls.student, room=cls.room, category=ComplaintCategory.ELECTRICAL,
            description="A light in the room is not working.",
        )
        Complaint.objects.filter(pk=cls.complaint.pk).update(
            created_at=timezone.now() - timedelta(days=4),
        )

    def test_report_index_lists_all_four_reports(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse("reports:index"))
        self.assertEqual(response.status_code, 200)
        for title in ("Occupancy Report", "Resident List", "Fee Dues Report", "Complaint Summary"):
            self.assertContains(response, title)

    def test_all_reports_render_required_fields_for_authorized_warden(self):
        self.client.force_login(self.warden)
        expected = {
            "occupancy": ["Room Number", "Occupied Beds", "Vacant Beds", "Occupancy %"],
            "residents": ["SRN", "Student Name", "Guardian Mobile", "Allocation Start Date"],
            "fee-dues": ["Annual Fee", "Amount Paid", "Balance", "Days Since Allocation"],
            "complaints": ["Complaint ID", "Category", "Raised On", "Days Open", "Resolved On", "Warden Remark"],
        }
        for report_type, headers in expected.items():
            with self.subTest(report=report_type):
                response = self.client.get(reverse("reports:detail", args=[report_type]))
                self.assertEqual(response.status_code, 200)
                for header in headers:
                    self.assertContains(response, header)
                self.assertEqual(len(response.context["report"]["rows"]), 1)

        occupancy = self.client.get(reverse("reports:detail", args=["occupancy"])).context["report"]["rows"][0]
        self.assertEqual((occupancy[4], occupancy[5], occupancy[6], occupancy[8]), (2, 1, 1, 50.0))
        resident = self.client.get(reverse("reports:detail", args=["residents"])).context["report"]["rows"][0]
        self.assertEqual(resident[:5], ["PES1UG24CS901", "Report Student", "Reports Block", "301", 1])
        dues = self.client.get(reverse("reports:detail", args=["fee-dues"])).context["report"]["rows"][0]
        self.assertEqual(dues[4:8], [Decimal("75000.00"), Decimal("0.00"), Decimal("75000.00"), 12])
        complaint = self.client.get(reverse("reports:detail", args=["complaints"])).context["report"]["rows"][0]
        self.assertEqual(complaint[3], "Electrical")
        self.assertEqual(complaint[6], 4)

    def test_hostel_and_date_filters_are_applied_to_reports_and_exports(self):
        self.client.force_login(self.warden)
        params = {
            "hostel": self.hostel.pk,
            "date_from": date.today().isoformat(),
            "date_to": date.today().isoformat(),
        }
        response = self.client.get(reverse("reports:detail", args=["residents"]), params)
        self.assertContains(response, "No records match the selected filters.")
        for report_type in ("fee-dues", "complaints"):
            filtered = self.client.get(reverse("reports:detail", args=[report_type]), params)
            self.assertEqual(filtered.context["report"]["rows"], [])
        occupancy = self.client.get(reverse("reports:detail", args=["occupancy"]), params)
        self.assertEqual(occupancy.context["report"]["rows"][0][5], 1)
        csv_response = self.client.get(
            reverse("reports:export", args=["residents", "csv"]), params,
        )
        self.assertEqual(csv_response.status_code, 200)
        self.assertNotContains(csv_response, "PES1UG24CS901")
        self.assertIn(b"SRN,Student Name", csv_response.content)

    def test_warden_cannot_view_or_export_another_hostels_data(self):
        self.client.force_login(self.warden)
        params = {"hostel": self.other_hostel.pk}
        detail = self.client.get(reverse("reports:detail", args=["occupancy"]), params)
        export = self.client.get(reverse("reports:export", args=["occupancy", "csv"]), params)
        self.assertEqual(detail.status_code, 400)
        self.assertEqual(export.status_code, 400)
        self.assertContains(detail, "Select a valid choice", status_code=400)

    def test_student_cannot_access_report_pages_or_exports(self):
        self.client.force_login(self.student_user)
        self.assertEqual(self.client.get(reverse("reports:index")).status_code, 403)
        self.assertEqual(
            self.client.get(reverse("reports:export", args=["occupancy", "csv"])).status_code, 403,
        )

    def test_administrator_can_report_across_hostels(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse("reports:detail", args=["occupancy"]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Reports Block")
        self.assertContains(response, "Other Reports Block")

    def test_csv_and_pdf_exports_contain_report_data_and_empty_results_are_valid(self):
        self.client.force_login(self.warden)
        csv_response = self.client.get(reverse("reports:export", args=["residents", "csv"]))
        self.assertEqual(csv_response["Content-Type"], "text/csv; charset=utf-8")
        self.assertIn(b"PES1UG24CS901", csv_response.content)
        pdf_response = self.client.get(reverse("reports:export", args=["residents", "pdf"]))
        self.assertEqual(pdf_response["Content-Type"], "application/pdf")
        self.assertTrue(pdf_response.content.startswith(b"%PDF-1.4"))
        self.assertIn(b"PES1UG24CS901", pdf_response.content)

        empty = self.client.get(reverse("reports:export", args=["complaints", "csv"]), {
            "date_from": (date.today() + timedelta(days=1)).isoformat(),
        })
        self.assertEqual(empty.status_code, 200)
        self.assertIn(b"Complaint ID", empty.content)
        self.assertNotIn(self.complaint.complaint_no.encode(), empty.content)
        empty_pdf = self.client.get(reverse("reports:export", args=["complaints", "pdf"]), {
            "date_from": (date.today() + timedelta(days=1)).isoformat(),
        })
        self.assertEqual(empty_pdf.status_code, 200)
        self.assertNotIn(self.complaint.complaint_no.encode(), empty_pdf.content)

    def test_invalid_date_range_is_rejected(self):
        self.client.force_login(self.warden)
        response = self.client.get(reverse("reports:detail", args=["complaints"]), {
            "date_from": date.today().isoformat(),
            "date_to": (date.today() - timedelta(days=1)).isoformat(),
        })
        self.assertEqual(response.status_code, 400)
        self.assertContains(response, "End date cannot be before start date.", status_code=400)
