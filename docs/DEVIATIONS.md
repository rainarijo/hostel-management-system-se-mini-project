# Deviations from the submitted SRS, SAD and Test Plan

Add one line per deviation (what changed, why, which document). These are explained at the final demo.

## Design and code

- Sprint 1 foundation: the SAD names the fee payment entity FEE_PAYMENT and the master list entity MASTER_LIST_ENTRY; the code uses `Payment` and `MasterStudent` (names kept from the skeleton, same fields).
- Sprint 1 foundation: failed-login counting lives on the User model (`failed_login_count`, `locked_until`) instead of a separate AUTH_ATTEMPT table (SAD 4.1.2). Same behaviour for FR-1.5.
- Sprint 1 foundation: service layers (`services.py`) are added feature by feature as each issue is built, not all at once.
- `validate_allocation_room` lives in `apps/rooms/validators.py` instead of `apps/allocation/services.py` (SAD 4.1.1), after it was lost in a bad merge during issue #11.
- The notification `enqueue()` function and kind names in `apps/notifications/services.py` were added under issue #6, because allocation needed them before the notifications issue delivered them.
- Check-out (FR-5.4) is available to Wardens only, although BR-1 also lists the Administrator (AL-1 in `docs/SECURITY_AUDIT.md`).

## Testing

- Concurrency (TC-10) is tested by simulating the race (patching the pre-check so the database constraint fires) instead of running two threads, because threaded tests are unreliable with Django TestCase and SQLite.
- NFR-USE-1: the usability results are simulated, as permitted by the instructor; no live test with 10 first-time users was run.
- SEC-REQ-4: the access-control audit found remaining low and medium issues (for example, some pages return 403 instead of 404 for another student's records). None expose another student's data. They are listed as known issues in `docs/SECURITY_AUDIT.md`.
- SEC-REQ-6: the OWASP ZAP baseline scan was run locally, not against a deployed server (date in the scan report).

## Performance

- Final verification (2026-11-01): Issue #18 production-like performance benchmarks remain unverified because a dedicated PostgreSQL/Gunicorn testing environment and access were unavailable during verification. A local Locust run was performed using SQLite and Django's development server; see `docs/FINAL_VERIFICATION.md`.
- NFR-PERF results were measured on a developer laptop with the Django development server, not on the reference VM with Gunicorn and PostgreSQL, so they are indicative only.
- Final verification (2026-11-01): the 10-user local Locust pages run encountered SQLite database locking while saving database-backed sessions (`SESSION_SAVE_EVERY_REQUEST = True`), followed by `SessionInterrupted` and HTTP 400. Concurrent SQLite session writes explain this limitation; see `docs/FINAL_VERIFICATION.md`.

## Deployment and operations

- The system is not deployed to the university VM described in SRS 2.4; it runs locally for development and the demo. CI runs the tests on PostgreSQL 16; local development uses SQLite.
- NFR-SAFE-1: backup and restore scripts and systemd timers are written for the Ubuntu VM in the SAD; they are not run in CI or on the Windows development machines, and have not run on a production VM because the project is not deployed. The consistency check itself is tested in CI.

## Process and schedule

- Issue #30 (e-mail notifications, FR-9.1/9.2) was moved into Sprint 1.
- PRs #45 and #47 were merged by their author before the "Protect main" ruleset was enabled; both were reviewed by the repository owner after merge.
- The Sprint 1 video was recorded on 25 Oct 2026 (sprint ended 23 Oct). The Sprint 2 video was recorded on 3 Nov 2026 (sprint ended 30 Oct).
- The Sprint 2 demo did not show a Warden updating complaint status because the Update link returned 404. In Sprint 3, the status page was fixed to render on GET and accept status changes via POST. The regression test test_warden_can_move_complaint_to_in_progress_through_page verifies the Warden can move a complaint to In Progress.
