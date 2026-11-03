# Deviations from the submitted SRS, SAD and Test Plan

Add one line per deviation (what changed, why, which document). These are explained at the final demo.

- Sprint 1 foundation: the SAD names the fee payment entity FEE_PAYMENT and the master list entity MASTER_LIST_ENTRY; the code uses `Payment` and `MasterStudent` (names kept from the skeleton, same fields).
- Sprint 1 foundation: failed-login counting lives on the User model (`failed_login_count`, `locked_until`) instead of a separate AUTH_ATTEMPT table (SAD 4.1.2). Same behaviour for FR-1.5.
- Sprint 1 foundation: service layers (`services.py`) are added feature by feature as each issue is built, not all at once.
- Concurrency (TC-10) is tested by simulating the race (patching the pre-check so the database constraint fires) instead of running two threads, because threaded tests are unreliable with Django TestCase and SQLite.
- NFR-SAFE-1: backup and restore scripts and systemd timers are written for the Ubuntu VM in the SAD; they are not run in CI or on the Windows development machines, and have not run on a production VM because the project is not deployed. The consistency check itself is tested in CI.
- Final verification (2026-11-01): Issue #18 production-like performance benchmarks remain unverified because a dedicated PostgreSQL/Gunicorn testing environment and access were unavailable during verification. A local Locust run was performed using SQLite and Django's development server; see `docs/FINAL_VERIFICATION.md`.
- NFR-PERF results were measured on a developer laptop with the Django development server, not on the reference VM with Gunicorn and PostgreSQL, so they are indicative only.
- Final verification (2026-11-01): the 10-user local Locust pages run encountered SQLite database locking while saving database-backed sessions (`SESSION_SAVE_EVERY_REQUEST = True`), followed by `SessionInterrupted` and HTTP 400. Concurrent SQLite session writes explain this limitation; see `docs/FINAL_VERIFICATION.md`.