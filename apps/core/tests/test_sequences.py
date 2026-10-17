"""Document numbers are sequential and per prefix (SAD 4.1.2)."""
from django.test import TestCase

from apps.core.sequences import next_number


class SequenceTests(TestCase):
    def test_numbers_are_sequential_per_prefix(self):
        self.assertEqual(next_number("APP", 2026), "APP-2026-00001")
        self.assertEqual(next_number("APP", 2026), "APP-2026-00002")
        self.assertEqual(next_number("CMP", 2026), "CMP-2026-00001")

    def test_new_year_restarts_the_count(self):
        next_number("APP", 2026)
        self.assertEqual(next_number("APP", 2027), "APP-2027-00001")
