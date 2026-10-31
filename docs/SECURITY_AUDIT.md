# Security audit: SEC-REQ-4 (authorisation, IDOR) and SEC-REQ-10 (secrets)

Issue #8, Test Plan TC-20. Audited on 30-10-2026 against `main` at 17fa075 (62 routes, Django admin excluded).

**How denials are handled.** Every protected view uses `apps.core.permissions.role_required`. It
redirects anonymous users to the login page and refuses the wrong role with a 403. It also logs every
denial as a WARNING on the `hms.security` logger with `security_event`, `user_id`, `method`, `path` and
`reason`. Users are identified by id only; e-mails, passwords, tokens, session ids, query strings and
request bodies are never logged, and `<token>` URL parts are redacted. The events are:

- `role_denied`: the user's role is not allowed on this route (403).
- `forbidden`: the view raised `PermissionDenied` or `AccessDenied`, or returned a 403.
- `not_found`: the view raised `Http404` or `ObjectNotFound`, or returned a 404.

`AccessDenied` and `ObjectNotFound` that escape a view become 403 and 404 (SAD 4.4.1).

**Tests** (in `apps/core/tests/`):
- **INV** `test_tc20_every_non_public_route_requires_login` walks every route as an anonymous user.
- **RM** `RoleMatrixTests` is the BR-1 role matrix and denial logging.
- **IDOR** `IdorTests` changes ids in URLs.
- **LOG** `SecurityLoggingTests`.
- **SEC10** `test_secrets.py`.

Feature tests named in the table live in each app's `tests/` folder.

## Route inventory

Roles: S = Student, W = Warden, A = Administrator, any = any logged-in user. "Scope" means the view also
restricts the data or object to the user's own records (Student) or own hostels (Warden).

| URL | Route name | Roles | Scope check | Tests |
|-----|------------|-------|-------------|-------|
| `accounts/login/` | accounts:login | public | n/a | accounts test_login |
| `accounts/logout/` | accounts:logout | any (POST only) | n/a | INV (405) |
| `accounts/register/` | accounts:register | public | n/a | accounts tests |
| `accounts/verify/<token>/` | accounts:verify_email | public | token | accounts test_tokens |
| `accounts/password-reset/` | accounts:password_reset | public | n/a | accounts tests |
| `accounts/password-reset/<token>/` | accounts:password_reset_confirm | public | token | accounts tests |
| `accounts/manage/` | accounts:account_list | A | n/a | INV, RM |
| `accounts/manage/create/` | accounts:account_create | A | n/a | INV, RM |
| `accounts/manage/<id>/role/` | accounts:account_change_role | A (POST only) | n/a | INV (405), RM (POST) |
| `accounts/manage/<id>/deactivate/` | accounts:account_deactivate | A (POST only) | n/a | INV (405), RM (POST) |
| `students/` | students:index | S, W, A | yes (S redirected to own profile) | INV |
| `students/profile/<id>/` | students:profile_detail | S, A | yes, but 403 not 404 (S-1) | INV, IDOR |
| `students/profile/<id>/edit/` | students:profile_edit | S, A | yes, but 403 not 404 (S-1) | INV, IDOR |
| `students/profile/<id>/photo/` | students:profile_photo | S, A | yes (404) | INV, IDOR |
| `students/profile/<id>/export.pdf` | students:profile_export_pdf | S, A | yes (404) | INV, IDOR |
| `students/search/` | students:search | W, A | yes (Warden's hostels) | INV, RM |
| `rooms/` | rooms:index | W, A | yes (R-2) | INV, RM |
| `rooms/hostels/new/` | rooms:hostel_create | A | n/a | INV, RM |
| `rooms/hostels/<id>/edit/` | rooms:hostel_edit | A | n/a | INV, RM |
| `rooms/hostels/<id>/deactivate/` | rooms:hostel_deactivate | A (POST) | n/a | INV, RM (POST) |
| `rooms/hostels/<id>/reactivate/` | rooms:hostel_reactivate | A (POST) | n/a | INV |
| `rooms/grid/` | rooms:room_grid | W, A | yes | INV, RM |
| `rooms/rooms/new/` | rooms:room_create | A | n/a | INV, RM |
| `rooms/rooms/<id>/edit/` | rooms:room_edit | A | n/a | INV, RM |
| `rooms/rooms/<id>/deactivate/` | rooms:room_deactivate | A (POST) | n/a | INV, rooms tests |
| `rooms/rooms/<id>/reactivate/` | rooms:room_reactivate | A (POST) | n/a | INV, rooms tests |
| `api/rooms/availability/` | room_availability_api | any (JSON 401 if anonymous) | yes (R-1) | INV (401), rooms tests |
| `manage/rooms/import/` | room_import | A | n/a | INV, RM |
| `allocation/` | allocation:index | S, W, A | n/a (placeholder) | INV |
| `applications/apply/` | allocation:apply | S | yes (own profile) | INV, test_apply |
| `applications/queue/` | allocation:queue | W, A | yes (gender of Warden's hostels) | INV, RM, test_queue |
| `applications/auto-allocate/` | allocation:auto_allocate | W, A (POST) | yes (404) | INV (405), RM, test_auto_allocate |
| `applications/<id>/allocate/` | allocation:allocate | W, A | yes (404) | INV, RM, IDOR, test_allocate |
| `applications/<id>/reject/` | allocation:reject | W, A (POST) | yes (404) | INV (405), IDOR, test_reject_confirm |
| `applications/<application_no>/` | allocation:application_detail | S | yes (own only, 404) | INV, IDOR, test_apply |
| `allocation/history/` | allocation:history | S | yes (own only) | INV, allocation tests |
| `manage/allocation-history/` | allocation:history_manage | W, A | yes | INV, RM |
| `room-change-requests/` | allocation:change_requests | S | yes (own only) | INV, allocation tests |
| `manage/room-change-requests/` | allocation:change_request_queue | W, A | yes | INV, RM |
| `manage/room-change-requests/<id>/approve/` | allocation:approve_change_request | W, A | yes (404) | INV, allocation tests |
| `manage/room-change-requests/<id>/reject/` | allocation:reject_change_request | W, A | yes (404) | INV, allocation tests |
| `manage/allocations/` | allocation:active_allocations | W (AL-1) | yes | INV, allocation tests |
| `manage/allocations/<id>/check-out/` | allocation:check_out | W (AL-1) | yes (404) | INV, allocation tests |
| `manage/windows/` | allocation:window_list | A | n/a | INV, RM, test_window |
| `manage/windows/new/` | allocation:window_create | A | n/a | INV, RM, test_window |
| `manage/windows/<id>/edit/` | allocation:window_edit | A | n/a | INV, RM |
| `complaints/` | complaints:index | S, W, A | yes (own / C-1) | INV, complaints tests |
| `complaints/<complaint_no>/status/` | complaints:change_status | W, A (POST) | yes (404, C-1, C-2) | INV, complaints tests |
| `complaints/<complaint_no>/reopen/` | complaints:reopen | S (POST) | yes (own only, 404) | INV, IDOR |
| `fees/` | fees:index | S (redirect), W, A | yes | INV, fees tests |
| `fees/my/` | fees:my_dues | S | yes (own only) | INV, fees tests |
| `fees/allocations/<id>/payments/` | fees:payment | W, A | yes, but 403 not 404 (F-1) | INV, fees tests |
| `fees/payments/<receipt_no>/receipt.pdf` | fees:receipt | S, W, A | yes, but 403 not 404 (F-1) | INV, IDOR |
| `fees/provisional-unpaid/` | fees:provisional_unpaid | W, A | yes | INV, RM |
| `reports/` | reports:index | W, A | n/a | INV, RM |
| `reports/<report_type>/` | reports:detail | W, A | yes (`scoped_hostels`) | INV, RM, reports tests |
| `reports/<report_type>/export/<format>/` | reports:export | W, A | yes (`scoped_hostels`) | INV, RM, reports tests |
| `notifications/` | notifications:index | S, W (N-1) | yes | INV, notifications tests |
| `notifications/announcements/post/` | notifications:post_announcement | W (N-1) | yes (form limited to own hostels) | INV, notifications tests |
| `` (site root) | core:home | any | n/a | INV, test_access_control |
| `dashboard/student/` | core:student_dashboard | S | yes (own) | INV, test_access_control |
| `dashboard/warden/` | core:warden_dashboard | W | yes | INV, RM, test_dashboards |
| `dashboard/admin/` | core:admin_dashboard | A | n/a | INV, RM, test_dashboards |
| `django-admin/core/auditlog/` | (Django admin) | superuser A only (`AuditLogAdmin`) | n/a | RM, test_access_control |

No route lets a user see data outside their role or scope. The problems below are mostly about which status
code is returned (403 where SEC-REQ-4 expects 404) and about roles that are stricter than BR-1. None of
them is fixed here because they are in other people's apps; the tests accept the current status where noted, so
CI stays green, and still check that no data leaks.

## Problems found in other apps

| ID | File | URL | Problem | Severity | Owner |
|----|------|-----|---------|----------|-------|
| S-1 | `apps/students/views.py` (`profile_detail`, `profile_edit`) | `students/profile/<id>/`, `.../edit/` | Another student's profile returns **403**, a missing one returns 404, so a student can tell which profile ids exist. SEC-REQ-4 / SAD 3.9 expect 404 for object-level access. No data is shown. Fix: use `get_authorized_profile` (already used by photo and PDF) and raise `Http404`. | Medium | Prema |
| A-1 | `apps/accounts/views.py` (`account_change_role`, `account_deactivate`) | `accounts/manage/<id>/role/`, `.../deactivate/` | `@require_POST` sits above `@role_required`, so a Student's GET gets 405 and is not logged as a role denial. POST is refused correctly (403). Fix: put `@role_required` first. | Low | Prema |
| R-1 | `apps/rooms/views.py` (`availability_api`) | `api/rooms/availability/` | Not under `role_required`, so its 403/404 JSON answers for out-of-scope hostels are not logged as `hms.security` events (only the role check calls `log_action`). | Low | Praakruthi |
| R-2 | `apps/rooms/views.py` (`index`) | `rooms/` | Warden scope is `Hostel.objects.filter(wardens=user)`, which includes deactivated hostels; every other module uses active hostels only (`scoped_hostels`). | Low | Praakruthi |
| C-1 | `apps/complaints/views.py` (`_warden_scope`) | `complaints/`, `complaints/<no>/status/` | Same as R-2: `room__hostel__wardens=user` includes deactivated hostels. | Low | Ojas |
| C-2 | `apps/complaints/views.py` (`change_complaint_status`, `reopen`) | `complaints/<no>/status/`, `.../reopen/` | A GET raises `Http404` instead of returning 405, so it is logged as a `not_found` security event (false alarm). Fix: `@require_POST`. | Low | Ojas |
| F-1 | `apps/fees/views.py` (`payment`, `receipt`) | `fees/allocations/<id>/payments/`, `fees/payments/<receipt_no>/receipt.pdf` | Out-of-scope objects get `HttpResponse("Forbidden", status=403)` instead of 404. Receipt numbers are sequential (RCP-YYYY-NNNNN), so 403 vs 404 tells a student which receipts exist. No PDF is returned. These answers are now logged centrally as `forbidden`. Fix: `raise Http404`. | Medium | Ojas |
| N-1 | `apps/notifications/views.py` (`index`, `post_announcement`) | `notifications/`, `notifications/announcements/post/` | Administrators get 403, but BR-1 lists "post announcements" for Warden **and** Admin. Too strict, not a leak. | Medium (BR-1 gap) | Ojas |

Found in my own app and **not** changed in this issue, because it is a behaviour decision for FR-5.4 (issue #14):

| ID | File | URL | Problem | Owner |
|----|------|-----|---------|-------|
| AL-1 | `apps/allocation/views.py`, `services.py` (`active_allocations`, `check_out_*`) | `manage/allocations/`, `.../check-out/` | Warden only, down to the service layer. BR-1 lists check-out for Warden **and** Admin. | Raina |

Not a problem, noted for completeness: the audit log can only be viewed in the Django admin, by superuser
Administrators (`AuditLogAdmin`). There is no in-app audit page.

## SEC-REQ-10 results

- `hms/settings.py` reads `DJANGO_SECRET_KEY`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT`,
  `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD` and the other settings from the environment. No real secret and no
  `django-insecure-` key is in the file. The only literal is the placeholder `dev-only-insecure-key-change-me`
  for local DEBUG runs; settings now refuse to start with it when `DJANGO_DEBUG` is off (SEC10 test).
- `.env.example` now lists all 16 variables settings.py reads (added the 6 e-mail variables and
  `HMS_SERVER_TIMING`), with placeholders only.
- `git ls-files`: `.env` is **not tracked**; only `.env.example` is. `.env` is ignored by `.gitignore` (line 5).
- `git log --all --oneline -- .env`: **no output**, so `.env` has never been committed on any branch. The only env
  files in the history are `.env.example` and an old `hostel-management-system/.env.example` (placeholders).
  No history rewrite is needed.
