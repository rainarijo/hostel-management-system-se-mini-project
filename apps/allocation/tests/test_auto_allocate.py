"""Tests for FR-4.7 Auto-Allocate (Test Plan TC-11, NFR-SAFE-2, SAD 4.1.5)."""
from datetime import timedelta
from unittest import mock

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import Role, User
from apps.allocation import services
from apps.allocation.models import (Allocation, ApplicationStatus, AutoAllocateRun, RoomApplication, RunStatus)
from apps.allocation.services import NO_PREFERRED_BED, auto_allocate
from apps.core.exceptions import BedUnavailable, RunInProgress
from apps.core.models import AuditLog
from apps.rooms.models import Hostel, Room, RoomStatus
from apps.students.models import StudentProfile

PASSWORD = "Strongpass2026"


class AutoAllocateTests(TestCase):
    def setUp(self):
        self.n = 0
        self.base = timezone.now() - timedelta(days=5)
        self.warden = User.objects.create_user("wb@hms.local", PASSWORD, role=Role.WARDEN)
        self.boys = Hostel.objects.create(name="Cauvery Block", gender_type="M")
        self.boys.wardens.add(self.warden)

    def make_room(self, room_no, room_type="SINGLE", capacity=1, floor=1, hostel=None, **extra):
        return Room.objects.create(hostel=hostel or self.boys, room_no=room_no, floor=floor, room_type=room_type,
                                   capacity=capacity, annual_fee=80000, **extra)

    def make_application(self, gender="M", year=2, flag=False, minutes=0, prefs=("SINGLE",), roommate=""):
        self.n += 1
        user = User.objects.create_user(f"s{self.n}@hms.local", PASSWORD, role=Role.STUDENT)
        student = StudentProfile.objects.create(user=user, srn=f"PES1UG24CS{self.n:03d}", name=f"Student {self.n}",
                                                gender=gender, program="B.Tech CSE", year=year, priority_flag=flag)
        prefs = list(prefs) + [""] * (3 - len(prefs))
        app = RoomApplication.objects.create(student=student, academic_year="2026-2027", preference_1=prefs[0],
                                             preference_2=prefs[1], preference_3=prefs[2],
                                             preferred_roommate_srn=roommate, application_no=f"APP-2026-{self.n:05d}")
        RoomApplication.objects.filter(pk=app.pk).update(submitted_at=self.base + timedelta(minutes=minutes))
        return app

    def status_of(self, application):
        application.refresh_from_db()
        return application.status

    def bed_of(self, application):
        allocation = Allocation.objects.active().filter(application=application).select_related("room").first()
        return (allocation.room.room_no, allocation.bed_no) if allocation else None

    def test_tc11_allocates_in_priority_order(self):
        self.make_room("101")
        self.make_room("102")
        self.make_room("103")
        other_old = self.make_application(minutes=1)
        priority_new = self.make_application(flag=True, minutes=6)
        year1_new = self.make_application(year=1, minutes=9)
        priority_old = self.make_application(flag=True, minutes=2)
        year1_old = self.make_application(year=1, minutes=3)

        summary = auto_allocate(self.boys, self.warden)

        self.assertEqual([r["application_no"] for r in summary["allocated"]],
                         [year1_old.application_no, year1_new.application_no, priority_old.application_no])
        self.assertEqual((self.bed_of(year1_old), self.bed_of(year1_new), self.bed_of(priority_old)),
                         (("101", 1), ("102", 1), ("103", 1)))
        self.assertEqual(self.status_of(priority_new), ApplicationStatus.PENDING)
        self.assertEqual(self.status_of(other_old), ApplicationStatus.PENDING)

    def test_tc11_uses_highest_available_preference(self):
        self.make_room("101", "SINGLE")
        self.make_room("201", "DOUBLE", capacity=2, floor=2)
        first = self.make_application(minutes=1, prefs=("SINGLE",))
        second = self.make_application(minutes=2, prefs=("SINGLE", "DOUBLE", "TRIPLE"))
        auto_allocate(self.boys, self.warden)
        self.assertEqual(self.bed_of(first), ("101", 1))
        self.assertEqual(self.bed_of(second), ("201", 1))

    def test_tc11_other_gender_applications_untouched(self):
        self.make_room("101", "DOUBLE", capacity=2)
        female = self.make_application(gender="F", minutes=1, prefs=("DOUBLE",))
        male = self.make_application(minutes=2, prefs=("DOUBLE",))
        summary = auto_allocate(self.boys, self.warden)
        self.assertEqual(self.status_of(female), ApplicationStatus.PENDING)
        self.assertFalse(Allocation.objects.filter(student=female.student).exists())
        self.assertEqual(self.status_of(male), ApplicationStatus.ALLOCATED)
        listed = [r["application_no"] for r in summary["allocated"] + summary["unallocated"]]
        self.assertNotIn(female.application_no, listed)

    def test_tc11_maintenance_rooms_skipped(self):
        self.make_room("101", status=RoomStatus.MAINTENANCE)
        self.make_room("102")
        application = self.make_application()
        auto_allocate(self.boys, self.warden)
        self.assertEqual(self.bed_of(application), ("102", 1))

    def test_tc11_unallocated_listed_and_stay_pending(self):
        self.make_room("101")
        self.make_application(minutes=1)
        late = self.make_application(minutes=2, prefs=("SINGLE", "TRIPLE"))
        summary = auto_allocate(self.boys, self.warden)
        self.assertEqual(summary["unallocated"], [{"application_no": late.application_no, "srn": late.student.srn,
                                                   "reason": NO_PREFERRED_BED}])
        self.assertEqual(self.status_of(late), ApplicationStatus.PENDING)

    def test_tc11_run_row_done_with_counts(self):
        self.make_room("101")
        self.make_application(minutes=1)
        self.make_application(minutes=2)
        summary = auto_allocate(self.boys, self.warden)
        run = AutoAllocateRun.objects.get()
        self.assertEqual(run, summary["run"])
        self.assertEqual((run.status, run.allocated_count, run.unallocated_count), (RunStatus.DONE, 1, 1))
        self.assertIsNotNone(run.finished_at)
        self.assertEqual(run.started_by, self.warden)
        self.assertTrue(AuditLog.objects.filter(action="AUTO_ALLOCATE", entity_id=str(run.pk),
                                                new_value="1 allocated, 1 unallocated").exists())

    def test_tc11_second_run_while_running_raises_run_in_progress(self):
        self.make_room("101")
        application = self.make_application()
        AutoAllocateRun.objects.create(hostel=self.boys, started_by=self.warden, status=RunStatus.RUNNING)
        with self.assertRaisesMessage(RunInProgress, "Auto-Allocate is already running for this hostel."):
            auto_allocate(self.boys, self.warden)
        self.assertEqual(self.status_of(application), ApplicationStatus.PENDING)
        self.assertEqual(AutoAllocateRun.objects.count(), 1)

    def test_tc11_unexpected_error_marks_run_failed(self):
        self.make_room("101")
        self.make_application()
        with mock.patch("apps.allocation.services.allocate", side_effect=RuntimeError("database went away")):
            with self.assertRaises(RuntimeError):
                auto_allocate(self.boys, self.warden)
        run = AutoAllocateRun.objects.get()
        self.assertEqual(run.status, RunStatus.FAILED)
        self.assertIsNotNone(run.finished_at)
        self.make_room("102")                                   # a failed run does not block the next one
        self.assertEqual(auto_allocate(self.boys, self.warden)["run"].status, RunStatus.DONE)

    def test_tc11_bed_taken_mid_run_moves_to_next_bed(self):
        self.make_room("101")
        self.make_room("102")
        application = self.make_application()
        real_allocate = services.allocate
        calls = []

        def taken_once(app, room, bed_no, actor):
            calls.append(room.room_no)
            if len(calls) == 1:
                raise BedUnavailable()                          # another Warden took 101 a moment ago
            return real_allocate(app, room, bed_no, actor)

        with mock.patch("apps.allocation.services.allocate", side_effect=taken_once):
            summary = auto_allocate(self.boys, self.warden)
        self.assertEqual(calls, ["101", "102"])
        self.assertEqual(self.bed_of(application), ("102", 1))
        self.assertEqual(len(summary["allocated"]), 1)

    def test_tc11_roommate_room_tried_first(self):
        self.make_room("101", "DOUBLE", capacity=2)
        room_202 = self.make_room("202", "DOUBLE", capacity=2, floor=2)
        friend = self.make_application(minutes=1, prefs=("DOUBLE",))
        Allocation.objects.create(student=friend.student, room=room_202, bed_no=1, application=friend,
                                  start_date=timezone.localdate())
        RoomApplication.objects.filter(pk=friend.pk).update(status=ApplicationStatus.ALLOCATED)
        application = self.make_application(minutes=2, prefs=("DOUBLE",), roommate=friend.student.srn)
        auto_allocate(self.boys, self.warden)
        self.assertEqual(self.bed_of(application), ("202", 2))   # not 101, which comes first by floor

    def test_tc11_roommate_given_bed_earlier_in_same_run(self):
        self.make_room("101", "TRIPLE", capacity=3)
        room_202 = self.make_room("202", "TRIPLE", capacity=3, floor=2)
        holder = self.make_application(prefs=("TRIPLE",))
        Allocation.objects.create(student=holder.student, room=room_202, bed_no=1, application=holder,
                                  start_date=timezone.localdate())
        RoomApplication.objects.filter(pk=holder.pk).update(status=ApplicationStatus.ALLOCATED)
        first = self.make_application(year=1, minutes=1, prefs=("TRIPLE",), roommate=holder.student.srn)
        second = self.make_application(minutes=2, prefs=("TRIPLE",), roommate=first.student.srn)
        auto_allocate(self.boys, self.warden)
        self.assertEqual(self.bed_of(first), ("202", 2))
        # "first" got 202 only in this run; "second" follows them there instead of taking 101.
        self.assertEqual(self.bed_of(second), ("202", 3))

    def test_tc11_warden_outside_scope_gets_404(self):
        girls = Hostel.objects.create(name="Kaveri Block", gender_type="F")
        self.client.login(email="wb@hms.local", password=PASSWORD)
        resp = self.client.post(reverse("allocation:auto_allocate"), {"hostel_id": girls.pk})
        self.assertEqual(resp.status_code, 404)
        self.assertFalse(AutoAllocateRun.objects.exists())
        self.assertEqual(self.client.post(reverse("allocation:auto_allocate"), {"hostel_id": "999"}).status_code,
                         404)

    def test_tc11_student_gets_403(self):
        application = self.make_application()
        self.client.login(email=application.student.user.email, password=PASSWORD)
        self.assertEqual(self.client.post(reverse("allocation:auto_allocate"),
                                          {"hostel_id": self.boys.pk}).status_code, 403)

    def test_tc11_get_returns_405(self):
        self.client.login(email="wb@hms.local", password=PASSWORD)
        self.assertEqual(self.client.get(reverse("allocation:auto_allocate")).status_code, 405)

    def test_tc11_view_shows_summary(self):
        self.make_room("101")
        allocated = self.make_application(minutes=1)
        unallocated = self.make_application(minutes=2)
        self.client.login(email="wb@hms.local", password=PASSWORD)
        self.assertContains(self.client.get(reverse("allocation:queue")), 'data-bs-target="#auto-allocate-confirm"')
        resp = self.client.post(reverse("allocation:auto_allocate"), {"hostel_id": self.boys.pk})
        self.assertContains(resp, "1 allocated, 1 unallocated")
        self.assertContains(resp, allocated.application_no)
        self.assertContains(resp, unallocated.application_no)
        self.assertContains(resp, NO_PREFERRED_BED)

    def test_tc11_view_run_in_progress_shows_banner_409(self):
        AutoAllocateRun.objects.create(hostel=self.boys, started_by=self.warden, status=RunStatus.RUNNING)
        self.client.login(email="wb@hms.local", password=PASSWORD)
        resp = self.client.post(reverse("allocation:auto_allocate"), {"hostel_id": self.boys.pk})
        self.assertContains(resp, "Auto-Allocate is already running for this hostel.", status_code=409)
