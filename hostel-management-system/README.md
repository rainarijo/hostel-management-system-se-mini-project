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
