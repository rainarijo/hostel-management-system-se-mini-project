"""chk_room_ranges: floor 0-20, capacity 1-4, annual fee 0-500000 (FR-3.2)."""
from django.db import IntegrityError, transaction
from django.test import TestCase

from apps.rooms.models import Hostel, Room


class RoomRangeTests(TestCase):
    def setUp(self):
        self.hostel = Hostel.objects.create(name="Range Block", gender_type="M")

    def make(self, **kw):
        data = dict(hostel=self.hostel, room_no="101", floor=1, room_type="DOUBLE", capacity=2, annual_fee=75000)
        data.update(kw)
        return Room.objects.create(**data)

    def test_valid_room_is_saved(self):
        self.assertEqual(self.make().capacity, 2)

    def test_capacity_above_four_is_rejected(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            self.make(capacity=5)

    def test_fee_above_limit_is_rejected(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            self.make(annual_fee=600000)
