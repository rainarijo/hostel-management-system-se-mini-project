from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from apps.accounts.models import Role, User
from apps.allocation.models import Allocation
from apps.students.models import StudentProfile


class StudentListScalabilityTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user("scale-admin@hms.local", "Strongpass2026", role=Role.ADMIN)
        users = User.objects.bulk_create([
            User(email=f"scale-student-{number}@hms.local", password="!", role=Role.STUDENT)
            for number in range(1, 102)
        ])
        StudentProfile.objects.bulk_create([
            StudentProfile(
                user=user,
                srn=f"SC{number:011d}",
                name=f"Scale Student {number}",
                gender="M",
                program="B.Tech CSE",
                year=2,
            )
            for number, user in enumerate(users, start=1)
        ])

    def test_admin_student_list_is_paginated(self):
        self.client.force_login(self.admin)

        first = self.client.get(reverse("students:index"))
        self.assertEqual(len(first.context["profiles"]), 50)
        self.assertContains(first, "Page 1 of 3")
        self.assertContains(first, "?page=2")

        last = self.client.get(reverse("students:index"), {"page": 3})
        self.assertEqual(len(last.context["profiles"]), 1)

    def test_search_prefetches_allocations_once_for_the_page(self):
        self.client.force_login(self.admin)

        with CaptureQueriesContext(connection) as captured:
            response = self.client.get(reverse("students:search"))

        allocation_queries = [
            query for query in captured.captured_queries
            if Allocation._meta.db_table in query["sql"]
        ]
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["results"]), 50)
        self.assertEqual(len(allocation_queries), 1)
        self.assertContains(response, "Page 1 of 3")

        last = self.client.get(reverse("students:search"), {"page": 3})
        self.assertEqual(len(last.context["results"]), 1)
