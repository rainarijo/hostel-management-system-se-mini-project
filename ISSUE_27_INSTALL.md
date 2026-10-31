# Issue #27 — Complaint status workflow

Branch:
`feature/27-complaint-status-workflow`

This package implements FR-6.3, FR-6.4 and FR-6.5 against the complaint implementation supplied for the project.

## Important integration note

The supplied `apps/complaints` package does not contain the `apps/notifications` implementation from Issue #30, and it does not contain the `apps/rooms` `HostelWarden` model.

Therefore this package does **not invent** the Issue #30 notification API or the exact `HostelWarden` field names.

The complaint code dynamically discovers the `HostelWarden` user/hostel foreign-key fields. If your `HostelWarden` model does not point directly to the authenticated User model and `rooms.Hostel`, stop and adapt `_warden_scope()` in `apps/complaints/views.py` before testing.

The notification enqueue must be connected to the existing Issue #30 notification service at the point marked in `apps/complaints/services.py` before merging #27, because FR-9.1 requires a queued email on every complaint status change.

## Files

Replace:
- `apps/complaints/services.py`
- `apps/complaints/forms.py`
- `apps/complaints/views.py`
- `apps/complaints/urls.py`

Add:
- `apps/complaints/tests/test_issue_27.py`
- `templates/complaints/warden_index.html`
- `templates/complaints/status_form.html`
- `templates/complaints/reopen_form.html`

No migration is included because the supplied Complaint model already contains:
- `status`
- `remark`
- `resolved_at`

## Behaviour

FR-6.3:
- Open -> In Progress
- Open -> Rejected
- In Progress -> Resolved
- In Progress -> Rejected
- every status change requires a remark
- invalid transitions are rejected

FR-6.4:
- only Resolved complaints can reopen
- reopening is allowed for 7 days after `resolved_at`
- reopening changes status to Open
- reopening clears `resolved_at`

FR-6.5:
- Open/In Progress complaints older than 72 hours are highlighted

## Installation

From the repository root, with the feature branch checked out:

1. Back up the current complaint files:

   `Copy-Item apps\complaints\services.py apps\complaints\services.py.bak`

   Repeat for `forms.py`, `views.py` and `urls.py` if desired.

2. Extract this ZIP into the repository root and allow the files to overwrite the matching paths.

3. Verify the project already has the complaint URL included in the root URL configuration.

4. Verify the project's base template is actually named `base.html`. If the project uses another base template, change the three supplied complaint templates to extend that existing template.

5. Verify `apps.rooms.models.HostelWarden` exists and represents the authenticated Warden-to-Hostel association.

6. Connect complaint status changes to the existing Issue #30 notification service. Do not create a second outbox implementation.

7. Run focused tests:

   `python manage.py test apps.complaints.tests.test_issue_27`
   `python manage.py test apps.complaints`

8. Run the full suite:

   `python manage.py test`

9. Run quality gates:

   `flake8 .`

   `git diff --check`

   `python manage.py makemigrations --check`

10. Inspect:

   `git diff --stat`

   `git diff`

11. Only after all checks pass, stage and commit:

   `git add apps/complaints templates/complaints`

   `git status`

   `git commit -m "Implement complaint status workflow for issue #27"`

12. Push:

   `git push -u origin feature/27-complaint-status-workflow`

Do not merge until CI is green.

## Manual acceptance checks

1. Student creates an Open complaint.
2. Warden sees it only when the complaint's room belongs to a hostel assigned to that Warden.
3. Warden can change Open -> In Progress with a remark.
4. Warden can change Open -> Rejected with a remark.
5. Warden can change In Progress -> Resolved with a remark.
6. Warden can change In Progress -> Rejected with a remark.
7. Warden cannot jump Open -> Resolved.
8. Warden cannot move Resolved -> In Progress.
9. Warden cannot submit a status change without a remark.
10. Student can reopen a complaint resolved 6 days ago.
11. Student cannot reopen one resolved 8 days ago.
12. Reopening returns status to Open.
13. An Open/In Progress complaint older than 72 hours appears highlighted on the Warden complaint dashboard.
14. A complaint status change produces the required Issue #30 notification through the existing notification service.
15. An audit entry is written in the same transaction as the status change.

## Do not skip

The uploaded complaint package alone is insufficient to verify the Issue #30 notification API and the exact HostelWarden model. Those two integration points must be checked against the actual repository before commit.
