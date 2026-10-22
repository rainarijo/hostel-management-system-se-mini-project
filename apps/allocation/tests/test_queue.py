"""Tests for FR-4.4: Warden application queue (SAD DD-1 scope rule)."""
from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import Role, User
from apps.allocation.models import ApplicationStatus, RoomApplication
from apps.allocation.services import list_pending
from apps.rooms.models import Hostel
from apps.students.models import StudentProfile

PASSWORD = "Strongpass2026"


class QueueTests(TestCase):
    def setUp(self):
        self.base = timezone.now() - timedelta(days=10)
        self.n = 0
        self.admin = User.objects.create_user("admin@hms.local", PASSWORD, role=Role.ADMIN)
        self.boys_warden = User.objects.create_user("wb@hms.local", PASSWORD, role=Role.WARDEN)
        self.girls_warden = User.objects.create_user("wg@hms.local", PASSWORD, role=Role.WARDEN)
        Hostel.objects.create(name="Boys Block", gender_type="M").wardens.add(self.boys_warden)
        Hostel.objects.create(name="Girls Block", gender_type="F").wardens.add(self.girls_warden)

    def make_application(self, gender="M", year=2, flag=False, minutes=0, pref="DOUBLE",
                         status=ApplicationStatus.PENDING):
        self.n += 1
        user = User.objects.create_user(f"s{self.n}@hms.local", PASSWORD, role=Role.STUDENT)
        student = StudentProfile.objects.create(user=user, srn=f"PES1UG24CS{self.n:03d}", name=f"Student {self.n}",
                                                gender=gender, program="B.Tech CSE", year=year, priority_flag=flag)
        app = RoomApplication.objects.create(student=student, academic_year="2026-2027", preference_1=pref,
                                             status=status, application_no=f"APP-2026-{self.n:05d}")
        # submitted_at is auto_now_add, so set it with update() to control the order.
        RoomApplication.objects.filter(pk=app.pk).update(submitted_at=self.base + timedelta(minutes=minutes))
        return app

    def test_fr44_ordering_year1_then_priority_then_others_oldest_first(self):
        other_old = self.make_application(minutes=1)
        priority_new = self.make_application(flag=True, minutes=5)
        year1_new = self.make_application(year=1, minutes=9)
        priority_old = self.make_application(flag=True, minutes=2)
        year1_old = self.make_application(year=1, minutes=3)
        other_new = self.make_application(minutes=8)
        expected = [year1_old, year1_new, priority_old, priority_new, other_old, other_new]
        self.assertEqual(list(list_pending(self.admin)), expected)

    def test_fr44_boys_warden_does_not_see_female_student(self):
        male, female = self.make_application(gender="M"), self.make_application(gender="F")
        self.assertEqual(list(list_pending(self.boys_warden)), [male])
        self.assertNotIn(female, list_pending(self.boys_warden))

    def test_fr44_girls_warden_does_not_see_male_student(self):
        male, female = self.make_application(gender="M"), self.make_application(gender="F")
        self.assertEqual(list(list_pending(self.girls_warden)), [female])
        self.client.login(email="wg@hms.local", password=PASSWORD)
        resp = self.client.get(reverse("allocation:queue"))
        self.assertContains(resp, female.application_no)
        self.assertNotContains(resp, male.application_no)

    def test_fr44_warden_without_hostels_sees_nothing(self):
        self.make_application()
        lonely = User.objects.create_user("wx@hms.local", PASSWORD, role=Role.WARDEN)
        self.assertFalse(list_pending(lonely).exists())

    def test_fr44_admin_sees_all(self):
        self.make_application(gender="M")
        self.make_application(gender="F")
        self.assertEqual(list_pending(self.admin).count(), 2)

    def test_fr44_student_gets_403(self):
        app = self.make_application()
        self.client.login(email=app.student.user.email, password=PASSWORD)
        self.assertEqual(self.client.get(reverse("allocation:queue")).status_code, 403)

    def test_fr44_year_and_room_type_filters(self):
        first = self.make_application(year=1, pref="SINGLE")
        second = self.make_application(year=2, pref="TRIPLE")
        third = self.make_application(year=2, pref="DOUBLE")
        RoomApplication.objects.filter(pk=third.pk).update(preference_2="SINGLE", preference_3="TRIPLE")
        self.assertEqual(list(list_pending(self.admin, year=2)), [second, third])
        self.assertEqual(list(list_pending(self.admin, preference="SINGLE")), [first, third])
        self.assertEqual(list(list_pending(self.admin, year=2, preference="TRIPLE")), [second, third])
        self.client.login(email="admin@hms.local", password=PASSWORD)
        resp = self.client.get(reverse("allocation:queue"), {"year": "1", "pref": "SINGLE"})
        self.assertEqual(list(resp.context["page"]), [first])

    def test_fr44_only_pending_listed(self):
        pending = self.make_application()
        for status in (ApplicationStatus.ALLOCATED, ApplicationStatus.REJECTED, ApplicationStatus.WITHDRAWN):
            self.make_application(status=status)
        self.assertEqual(list(list_pending(self.admin)), [pending])

    def test_fr44_26_applications_paginate_into_25_and_1(self):
        for i in range(26):
            self.make_application(minutes=i)
        self.client.login(email="admin@hms.local", password=PASSWORD)
        url = reverse("allocation:queue")
        first = self.client.get(url, {"year": "2"})
        self.assertEqual(len(first.context["page"]), 25)
        self.assertContains(first, "?year=2&amp;page=2")
        second = self.client.get(url, {"year": "2", "page": "2"})
        self.assertEqual(len(second.context["page"]), 1)
