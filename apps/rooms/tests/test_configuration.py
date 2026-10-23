"""Tests for FR-3.1 and FR-3.2 hostel and room configuration."""
from datetime import date
from unittest.mock import patch

from django.db import IntegrityError, transaction
from django.db.models.deletion import ProtectedError
from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import Role, User
from apps.allocation.models import Allocation
from apps.core.models import AuditLog
from apps.rooms.models import Hostel, Room
from apps.students.models import StudentProfile

PASSWORD = "Strongpass2026"


class ConfigurationTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user("admin@hms.local", PASSWORD, role=Role.ADMIN)
        self.warden = User.objects.create_user("warden@hms.local", PASSWORD, role=Role.WARDEN)
        self.student = User.objects.create_user("student@hms.local", PASSWORD, role=Role.STUDENT)
        self.hostel = Hostel.objects.create(name="North Hall", gender_type="M")

    def login(self, user):
        self.client.force_login(user)

    def post_room(self, **overrides):
        values = {
            "hostel": self.hostel.pk,
            "room_no": "101",
            "floor": 1,
            "room_type": "DOUBLE",
            "capacity": 2,
            "annual_fee": "75000.00",
            "status": "AVAILABLE",
        }
        values.update(overrides)
        return self.client.post(reverse("rooms:room_create"), values)

    def test_fr31_fr32_admin_pages_render(self):
        self.login(self.admin)
        paths = (
            reverse("rooms:index"),
            reverse("rooms:hostel_create"),
            reverse("rooms:hostel_edit", args=[self.hostel.pk]),
            reverse("rooms:room_create"),
        )
        for path in paths:
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 200)

    def test_fr31_admin_can_create_hostel_with_assigned_warden(self):
        self.login(self.admin)
        response = self.client.post(reverse("rooms:hostel_create"), {
            "name": "South Hall", "gender_type": "F", "wardens": [self.warden.pk],
        })
        self.assertRedirects(response, reverse("rooms:index"))
        hostel = Hostel.objects.get(name="South Hall")
        self.assertEqual(hostel.gender_type, "F")
        self.assertEqual(list(hostel.wardens.all()), [self.warden])
        self.assertTrue(AuditLog.objects.filter(action="HOSTEL_CREATED", entity_id=str(hostel.pk)).exists())

    def test_fr31_hostel_requires_at_least_one_warden(self):
        self.login(self.admin)
        response = self.client.post(reverse("rooms:hostel_create"), {
            "name": "South Hall", "gender_type": "F", "wardens": [],
        })
        self.assertEqual(response.status_code, 200)
        self.assertIn("wardens", response.context["form"].errors)
        self.assertFalse(Hostel.objects.filter(name="South Hall").exists())

    def test_fr31_hostel_name_must_be_unique_and_assignments_must_be_wardens(self):
        self.login(self.admin)
        response = self.client.post(reverse("rooms:hostel_create"), {
            "name": self.hostel.name, "gender_type": "F", "wardens": [self.warden.pk],
        })
        self.assertEqual(response.status_code, 200)
        self.assertIn("name", response.context["form"].errors)

        response = self.client.post(reverse("rooms:hostel_create"), {
            "name": "South Hall", "gender_type": "F", "wardens": [self.student.pk],
        })
        self.assertEqual(response.status_code, 200)
        self.assertIn("wardens", response.context["form"].errors)
        self.assertFalse(Hostel.objects.filter(name="South Hall").exists())

    def test_fr31_database_integrity_error_is_shown_on_form(self):
        self.login(self.admin)
        with patch("apps.rooms.forms.HostelForm.save", side_effect=IntegrityError):
            response = self.client.post(reverse("rooms:hostel_create"), {
                "name": "South Hall", "gender_type": "F", "wardens": [self.warden.pk],
            })
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["form"].non_field_errors())
        self.assertFalse(Hostel.objects.filter(name="South Hall").exists())

    def test_fr31_admin_can_edit_hostel_and_audit_old_and_new_values(self):
        self.hostel.wardens.add(self.warden)
        self.login(self.admin)
        response = self.client.post(reverse("rooms:hostel_edit", args=[self.hostel.pk]), {
            "name": "North Hall Updated", "gender_type": "F", "wardens": [self.warden.pk],
        })
        self.assertRedirects(response, reverse("rooms:index"))
        self.hostel.refresh_from_db()
        self.assertEqual(self.hostel.name, "North Hall Updated")
        audit = AuditLog.objects.get(action="HOSTEL_UPDATED")
        self.assertIn("North Hall", audit.old_value)
        self.assertIn("North Hall Updated", audit.new_value)

    def test_fr31_hostel_deactivation_requires_post_and_is_audited(self):
        self.login(self.admin)
        url = reverse("rooms:hostel_deactivate", args=[self.hostel.pk])
        self.assertEqual(self.client.get(url).status_code, 405)
        response = self.client.post(url)
        self.assertRedirects(response, reverse("rooms:index"))
        self.hostel.refresh_from_db()
        self.assertFalse(self.hostel.is_active)
        self.assertTrue(AuditLog.objects.filter(action="HOSTEL_DEACTIVATED",
                                                entity_id=str(self.hostel.pk)).exists())

    def test_fr35_room_and_hostel_deactivation_reject_active_allocations(self):
        room = Room.objects.create(hostel=self.hostel, room_no="101", floor=1, room_type="DOUBLE",
                                   capacity=2, annual_fee=75000)
        profile = StudentProfile.objects.create(
            user=self.student, srn="PES1UG24CS7001", name="Integrity Student",
            gender="M", program="B.Tech CSE", year=1)
        Allocation.objects.create(student=profile, room=room, bed_no=1, start_date=date.today())
        self.login(self.admin)

        response = self.client.post(reverse("rooms:room_deactivate", args=[room.pk]), follow=True)
        self.assertContains(response, "Room has active allocations")
        room.refresh_from_db()
        self.assertTrue(room.is_active)
        self.assertFalse(AuditLog.objects.filter(action="ROOM_DEACTIVATED").exists())

        response = self.client.post(reverse("rooms:hostel_deactivate", args=[self.hostel.pk]), follow=True)
        self.assertContains(response, "Hostel has active allocations")
        self.hostel.refresh_from_db()
        self.assertTrue(self.hostel.is_active)
        self.assertFalse(AuditLog.objects.filter(action="HOSTEL_DEACTIVATED").exists())

    def test_fr35_room_and_hostel_deactivation_can_be_reversed(self):
        room = Room.objects.create(hostel=self.hostel, room_no="101", floor=1, room_type="DOUBLE",
                                   capacity=2, annual_fee=75000)
        self.login(self.admin)

        self.client.post(reverse("rooms:room_deactivate", args=[room.pk]))
        room.refresh_from_db()
        self.assertFalse(room.is_active)
        response = self.client.post(reverse("rooms:room_reactivate", args=[room.pk]), follow=True)
        room.refresh_from_db()
        self.assertTrue(room.is_active)
        self.assertContains(response, "reactivated")

        self.client.post(reverse("rooms:hostel_deactivate", args=[self.hostel.pk]))
        self.hostel.refresh_from_db()
        self.assertFalse(self.hostel.is_active)
        response = self.client.post(reverse("rooms:hostel_reactivate", args=[self.hostel.pk]), follow=True)
        self.hostel.refresh_from_db()
        self.assertTrue(self.hostel.is_active)
        self.assertContains(response, "reactivated")
        self.assertTrue(AuditLog.objects.filter(action="ROOM_DEACTIVATED").exists())
        self.assertTrue(AuditLog.objects.filter(action="ROOM_REACTIVATED").exists())
        self.assertTrue(AuditLog.objects.filter(action="HOSTEL_DEACTIVATED").exists())
        self.assertTrue(AuditLog.objects.filter(action="HOSTEL_REACTIVATED").exists())

    def test_fr35_rooms_and_hostels_cannot_be_physically_deleted(self):
        room = Room.objects.create(hostel=self.hostel, room_no="101", floor=1, room_type="DOUBLE",
                                   capacity=2, annual_fee=75000)
        admin = User.objects.create_superuser("delete-admin@hms.local", PASSWORD)
        self.login(admin)
        self.assertEqual(self.client.get(reverse("admin:rooms_room_delete", args=[room.pk])).status_code, 403)
        self.assertEqual(self.client.get(reverse("admin:rooms_hostel_delete", args=[self.hostel.pk])).status_code, 403)

        with self.assertRaises(ProtectedError), transaction.atomic():
            room.delete()
        with self.assertRaises(ProtectedError), transaction.atomic():
            Room.objects.filter(pk=room.pk).delete()
        with self.assertRaises(ProtectedError), transaction.atomic():
            Hostel.objects.filter(pk=self.hostel.pk).delete()
        self.assertTrue(Room.objects.filter(pk=room.pk).exists())
        self.assertTrue(Hostel.objects.filter(pk=self.hostel.pk).exists())

    def test_fr32_admin_can_create_and_edit_room_with_audit(self):
        self.login(self.admin)
        response = self.post_room(floor=0, capacity=1, room_type="SINGLE", annual_fee="0.00", status="AVAILABLE")
        self.assertRedirects(response, reverse("rooms:index"))
        room = Room.objects.get(hostel=self.hostel, room_no="101")
        self.assertEqual(room.floor, 0)
        self.assertEqual(room.annual_fee, 0)
        self.assertEqual(room.status, "AVAILABLE")
        self.assertTrue(AuditLog.objects.filter(action="ROOM_CREATED", entity_id=str(room.pk)).exists())

        response = self.client.post(reverse("rooms:room_edit", args=[room.pk]), {
            "hostel": self.hostel.pk, "room_no": "102", "floor": 20, "room_type": "TRIPLE",
            "capacity": 4, "annual_fee": "500000.00", "status": "MAINTENANCE",
        })
        self.assertRedirects(response, reverse("rooms:index"))
        room.refresh_from_db()
        self.assertEqual((room.room_no, room.floor, room.capacity), ("102", 20, 4))
        self.assertEqual(room.annual_fee, 500000)
        audit = AuditLog.objects.get(action="ROOM_UPDATED")
        self.assertIn("room: 101", audit.old_value)
        self.assertIn("room: 102", audit.new_value)

    def test_fr32_room_bounds_and_choices_are_validated(self):
        self.login(self.admin)
        for invalid in (
            {"floor": -1}, {"floor": 21}, {"capacity": 0}, {"capacity": 5},
            {"annual_fee": "-0.01"}, {"annual_fee": "500000.01"},
            {"room_type": "QUADRUPLE"}, {"status": "OCCUPIED"},
        ):
            with self.subTest(invalid=invalid):
                response = self.post_room(**invalid)
                self.assertEqual(response.status_code, 200)
                self.assertFalse(Room.objects.filter(hostel=self.hostel).exists())

    def test_fr32_room_status_must_match_occupancy(self):
        self.login(self.admin)
        response = self.post_room(status="FULL")
        self.assertEqual(response.status_code, 200)
        self.assertIn("status", response.context["form"].errors)
        self.assertFalse(Room.objects.filter(hostel=self.hostel).exists())

        self.assertEqual(self.post_room().status_code, 302)
        room = Room.objects.get(hostel=self.hostel)
        response = self.client.post(reverse("rooms:room_edit", args=[room.pk]), {
            "hostel": self.hostel.pk, "room_no": room.room_no, "floor": room.floor,
            "room_type": room.room_type, "capacity": room.capacity, "annual_fee": room.annual_fee,
            "status": "FULL",
        })
        self.assertEqual(response.status_code, 200)
        self.assertIn("status", response.context["form"].errors)
        room.refresh_from_db()
        self.assertEqual(room.status, "AVAILABLE")

    def test_fr32_capacity_cannot_be_reduced_below_active_occupancy(self):
        from datetime import date

        from apps.allocation.models import Allocation
        from apps.students.models import StudentProfile

        self.login(self.admin)
        self.assertEqual(self.post_room().status_code, 302)
        room = Room.objects.get(hostel=self.hostel)
        students = []
        for number in (1, 2):
            user = User.objects.create_user(f"capacity{number}@hms.local", PASSWORD, role=Role.STUDENT)
            students.append(StudentProfile.objects.create(
                user=user, srn=f"PES1UG24CS8{number:02d}", name=f"Capacity Student {number}",
                gender="M", program="B.Tech CSE", year=1))
        for bed_no, student in enumerate(students, start=1):
            Allocation.objects.create(student=student, room=room, bed_no=bed_no, start_date=date.today())

        response = self.client.post(reverse("rooms:room_edit", args=[room.pk]), {
            "hostel": self.hostel.pk, "room_no": room.room_no, "floor": room.floor,
            "room_type": room.room_type, "capacity": 1, "annual_fee": room.annual_fee, "status": "FULL",
        })
        self.assertEqual(response.status_code, 200)
        self.assertIn("capacity", response.context["form"].errors)
        room.refresh_from_db()
        self.assertEqual(room.capacity, 2)

    def test_fr32_room_number_must_be_unique_within_hostel(self):
        self.login(self.admin)
        self.assertEqual(self.post_room().status_code, 302)
        response = self.post_room(hostel=self.hostel.pk, room_no="101")
        self.assertEqual(response.status_code, 200)
        self.assertIn("__all__", response.context["form"].errors)

        other_hostel = Hostel.objects.create(name="South Hall", gender_type="F")
        response = self.post_room(hostel=other_hostel.pk, room_no="101")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Room.objects.filter(room_no="101").count(), 2)

    def test_fr32_database_integrity_error_is_shown_on_form(self):
        self.login(self.admin)
        with patch("apps.rooms.forms.RoomForm.save", side_effect=IntegrityError):
            response = self.post_room()
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["form"].non_field_errors())
        self.assertFalse(Room.objects.filter(hostel=self.hostel).exists())

    def test_fr32_only_administrator_can_change_configuration(self):
        for user in (self.warden, self.student):
            self.login(user)
            for name, args in (
                ("rooms:hostel_create", ()),
                ("rooms:hostel_edit", (self.hostel.pk,)),
                ("rooms:hostel_deactivate", (self.hostel.pk,)),
                ("rooms:hostel_reactivate", (self.hostel.pk,)),
                ("rooms:room_create", ()),
                ("rooms:room_edit", (1,)),
                ("rooms:room_deactivate", (1,)),
                ("rooms:room_reactivate", (1,)),
            ):
                response = self.client.post(reverse(name, args=args), {})
                self.assertEqual(response.status_code, 403, (user.role, name))

    def test_anonymous_users_are_redirected_from_configuration_pages(self):
        paths = (
            reverse("rooms:index"),
            reverse("rooms:hostel_create"),
            reverse("rooms:hostel_edit", args=[self.hostel.pk]),
            reverse("rooms:hostel_deactivate", args=[self.hostel.pk]),
            reverse("rooms:hostel_reactivate", args=[self.hostel.pk]),
            reverse("rooms:room_create"),
            reverse("rooms:room_edit", args=[1]),
            reverse("rooms:room_deactivate", args=[1]),
            reverse("rooms:room_reactivate", args=[1]),
        )
        for path in paths:
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 302)
                self.assertIn(reverse("accounts:login"), response["Location"])

    def test_warden_can_view_assigned_configuration_but_not_other_hostels(self):
        self.hostel.wardens.add(self.warden)
        Hostel.objects.create(name="South Hall", gender_type="F")
        self.login(self.warden)
        response = self.client.get(reverse("rooms:index"))
        self.assertContains(response, "North Hall")
        self.assertNotContains(response, "South Hall")
        self.assertEqual(response.context["hostels"].count(), 1)
        self.assertEqual(response.context["rooms"].count(), 0)
