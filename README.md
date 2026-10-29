# Hostel Management System (HMS)

SE Mini-Project, Group 3, PES University (Dept. of CSE).
Raina Kareem (PES1UG24CS361), Prema P Kotur (PES1UG24CS343), Praakruthi PS (PES1UG24CS324), Ojas Taori (PES1UG24CS308).

A Django web application to manage hostel room allocation and student details.
Requirements are in [`docs/SRS_Hostel_Management_System.pdf`](docs/SRS_Hostel_Management_System.pdf);
requirement IDs (FR-x.y, SEC-REQ-n, ...) are referenced in the code comments.

## Run it on your laptop

You need **Python 3.12**, **Git** and **VS Code** (with the Python extension).

```bash
git clone <repo-url>
cd hostel-management-system

python -m venv .venv
# Windows:      .venv\Scripts\activate
# macOS/Linux:  source .venv/bin/activate

pip install -r requirements.txt
cp .env.example .env            # Windows: copy .env.example .env

python manage.py migrate
python manage.py seed_data      # sample hostels, rooms, users
python manage.py runserver
```

Open http://127.0.0.1:8000 and log in. Every sample account uses the password `Hostel2026pass`:

| Role | E-mail |
|---|---|
| Administrator | admin@hms.local |
| Warden (boys' block) | warden.boys@hms.local |
| Warden (girls' block) | warden.girls@hms.local |
| Students | student1@hms.local ... student6@hms.local |

The developer data browser is at http://127.0.0.1:8000/django-admin/ (log in as admin).
It is for checking data while developing, not the Administrator screens we build.

The default database is SQLite (zero setup). To use PostgreSQL 16, as the SRS requires for
deployment, set `DB_ENGINE=postgres` and the `DB_*` values in `.env`.

## Project layout

```
hms/                 project settings and root URLs
apps/
  core/              dashboards, role_required decorator, audit log, seed_data command
  accounts/          C1  login, lock-out, roles, registration           FR-1.x
  students/          C2  student profiles, master list, search         FR-2.x
  rooms/             C3  hostels, rooms, occupancy                     FR-3.x
  allocation/        C4  application window, applications, allocation, room change   FR-4.x, FR-5.x
  complaints/        C5  complaints                                     FR-6.x
  fees/              C6  fee records, payments, receipts               FR-7.x
  reports/           C7  reports and exports                            FR-8.x
  notifications/     C8  e-mail log, announcements                      FR-9.x
templates/           HTML templates (base layout, dashboards, per-app folders)
static/              CSS and Bootstrap (served locally)
docs/                SRS and other project documents
```

Each app has `models.py`, `views.py`, `urls.py`, `admin.py` and a `tests/` folder.
Screens not built yet show a "coming soon" page that names the FRs and planned sprint.

### Rules already in place

- Custom user model with roles (`apps/accounts/models.py`). Protect views with
  `@role_required(Role.WARDEN, Role.ADMIN)` from `apps/core/permissions.py`.
- Record data changes with `log_action(...)` from `apps/core/audit.py` (SEC-REQ-8).
- Double allocation is blocked by database constraints on `Allocation` (FR-4.6).
- Lock-out after 5 failed logins, 30-minute session timeout, password policy (FR-1.5, FR-1.7, SEC-REQ-2).

## How we work

- **Board**: GitHub Projects (Backlog, Sprint, In progress, Review, Done). One issue per user story,
  labelled with its FR IDs and sprint.
- **Branches**: never commit straight to `main`. Create a branch per issue, e.g. `feature/12-apply-for-room`.
- **Pull requests**: open a PR into `main`, link the issue (`Closes #12`), and get one teammate's approval.
  CI (`.github/workflows/ci.yml`) must pass: flake8, migration check, and tests on PostgreSQL.
- **Tests**: name test methods after Test Plan IDs, e.g. `test_tc10_same_bed_cannot_be_allocated_twice`.

```bash
python manage.py test           # run all tests
flake8                          # style check (NFR-MNT-1)
python manage.py makemigrations # after changing any models.py, then commit the migration file
```

### Performance and load tests

Issue #18 sets the interactive-page target at 200 concurrent users: p95 no more than 2 seconds and
no request over 5 seconds. The SAD also cites the separate SRS targets of an allocation within
1 second and auto-allocation of 500 applications within 60 seconds. Those allocation targets are
not interchangeable with the page-response target.

The SAD's OI-5 notes that a 100% under-5-second guarantee cannot be established by a finite load
test and suggests interpreting that bound as either p99 or the observed maximum. Issue #18 retains
the explicit 100% acceptance wording, so this harness checks the observed maximum for the run; it
does not claim a lifetime guarantee. Confirm whether the intended bound is an observed maximum or
p99 before changing that acceptance criterion.

Run load tests only against a dedicated PostgreSQL/Gunicorn deployment (not the development
SQLite database or Django's `runserver`). Start with the normal sample accounts, then seed an
isolated test database with synthetic records:

```powershell
python manage.py seed_data
python manage.py seed_performance_data --students 5000 --beds 4000
```

The performance-data command adds one synthetic hostel and the requested number of students and
beds, with active allocations, fee records, pending applications, and complaints. Generated
student accounts are inactive and have unusable passwords. The command refuses to overwrite an
existing `HMS Load Test Hostel`; use a clean, disposable database and run it only once.

Install Locust separately from the application's runtime dependencies, and enable Django request
timings on the server:

```powershell
.venv\Scripts\python.exe -m pip install -r requirements-performance.txt
$env:HMS_SERVER_TIMING = "1"
```

From a separate load-generator machine, run the 200-user interactive-page test:

```powershell
locust -f perf/locustfile.py --host https://<test-host> --users 200 --spawn-rate 10 `
  --run-time 5m --headless --tags pages --html performance-results.html
```

The Locust users exercise student, Warden, and Administrator dashboards; student search and
profiles; allocation queue/options and active allocations; and reports. The test fails with a
non-zero exit status if client-observed or Django-measured p95 exceeds 2 seconds, a maximum exceeds
5 seconds, a request fails, or the server timing header is missing. Django timing measures
middleware-to-response processing; Locust's standard timings additionally include worker queuing
and network time. Review both sets of results and the per-page Locust statistics.

To measure the SAD's 500-application auto-allocation limit separately, seed an isolated database
with 1,000 students and 1,000 beds (half are allocated, leaving 500 pending applications and 500
vacant beds), then run the one-user mode:

```powershell
python manage.py seed_performance_data --students 1000 --beds 1000
$env:HMS_LOADTEST_MODE = "auto_allocate"
locust -f perf/locustfile.py --host https://<test-host> --users 1 --spawn-rate 1 `
  --run-time 2m --headless --tags auto_allocate
```

This mode makes one Auto-Allocate request and fails if client or Django processing exceeds
60 seconds. It changes the test data by allocating pending students, so do not reuse that database
for a second run. Results from these commands are measurements only when the commands are actually
run; no performance result is implied by passing the ordinary unit tests.

The SAD's individual-allocation target can also be measured in isolation. Use a fresh scale dataset
and run one allocation request; this consumes a pending application:

```powershell
python manage.py seed_performance_data --students 5000 --beds 4000
$env:HMS_LOADTEST_MODE = "allocation"
locust -f perf/locustfile.py --host https://<test-host> --users 1 --spawn-rate 1 `
  --run-time 1m --headless --tags allocation
```

This mode fails if the individual allocation exceeds 1 second at either the client or Django
measurement boundary.
