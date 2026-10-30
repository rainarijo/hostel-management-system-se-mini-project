"""NFR-REL-1: run daily at 01:30 IST by ops/systemd/hms-consistency.timer (SAD 4.1.7).

Exit code 0 when clean, 1 on any finding (so systemd marks the run as failed).
"""
import logging

from django.core.mail import send_mail
from django.core.management.base import BaseCommand

from apps.accounts.models import Role, User
from apps.allocation.consistency import find_inconsistencies

logger = logging.getLogger("hms.consistency")


class Command(BaseCommand):
    help = "Check for double-booked beds and room statuses that disagree with occupancy (NFR-REL-1)."

    def add_arguments(self, parser):
        parser.add_argument("--no-email", action="store_true", help="Report only; do not e-mail the Administrators.")

    def handle(self, *args, **options):
        double_booked, mismatches = find_inconsistencies()
        if not double_booked and not mismatches:
            self.stdout.write(self.style.SUCCESS("OK: 0 double-booked beds, 0 room status mismatches"))
            return

        lines = [f"DOUBLE-BOOKED: {room} bed {bed_no} has {count} active allocations"
                 for room, bed_no, count in double_booked]
        lines += [f"STATUS MISMATCH: {room} is stored as {stored}, expected {expected}"
                  for room, stored, expected in mismatches]
        summary = f"{len(double_booked)} double-booked beds, {len(mismatches)} room status mismatches"
        for line in lines:
            self.stdout.write(line)
            logger.error(line)
        self.stdout.write(self.style.ERROR(f"FAILED: {summary}"))

        if not options["no_email"]:
            # No outbox kind exists for this operational alert, so it is sent directly.
            recipients = list(User.objects.filter(role=Role.ADMIN, is_active=True)
                              .exclude(email="").values_list("email", flat=True))
            if recipients:
                send_mail(f"[HMS] Nightly consistency check: {summary}",
                          "The nightly consistency check (NFR-REL-1) found:\n\n" + "\n".join(lines),
                          None, recipients)
            else:
                logger.error("No active Administrator to notify about: %s", summary)
        raise SystemExit(1)
